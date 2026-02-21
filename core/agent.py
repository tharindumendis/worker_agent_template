"""
core/agent.py
-------------
The heart of the Worker Agent.

Responsibilities:
1. Read config to know which MCP servers to connect to.
2. Dynamically load all tools from those MCP servers (connections stay alive).
3. Build a LangGraph ReAct loop with those tools + the local Ollama LLM.
4. Log every single step to a per-job file via JobLogger.
5. Expose run_agent(task, config) -> str used by main.py.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import warnings
from contextlib import AsyncExitStack
from typing import List, Optional

# Suppress LangGraph deprecation noise
warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

from core.config_loader import AppConfig, MCPClientConfig
from core.job_logger import JobLogger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tool_input(tool_call: dict) -> dict:
    """Extract input args from a LangChain tool call dict."""
    return tool_call.get("args", {}) or {}


def _truncate(text: str, max_chars: int = 800) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [{len(text) - max_chars} chars truncated]"


# ---------------------------------------------------------------------------
# Main entry-point — called by main.py for every execute_task() invocation
# ---------------------------------------------------------------------------

async def run_agent(task: str, config: AppConfig) -> str:
    """
    Execute a task using the full ReAct loop with per-job structured logging.

    - One JobLogger (= one log file) is created per call.
    - All MCP connections remain open for the entire loop duration.
    - Every LLM output, tool call, tool result and error is logged as a step.

    Args:
        task:   The natural-language instruction for this worker.
        config: The loaded AppConfig from config.yaml.

    Returns:
        str: The final answer produced by the agent.
    """
    jl = JobLogger(task=task, agent_name=config.agent.name)
    logger.info("[%s] Job %s started | task: %s", config.agent.name, jl.job_id, task[:80])

    all_tools: List[BaseTool] = []
    final_answer = ""
    success = False

    try:
        # ----------------------------------------------------------------
        # PHASE 1 — Connect to all MCP tool servers
        # ----------------------------------------------------------------
        async with AsyncExitStack() as stack:
            for client_cfg in config.mcp_clients:
                server_params = StdioServerParameters(
                    command=client_cfg.command,
                    args=client_cfg.args,
                    env=client_cfg.env or None,
                )
                try:
                    read, write = await stack.enter_async_context(
                        stdio_client(server_params)
                    )
                    session: ClientSession = await stack.enter_async_context(
                        ClientSession(read, write)
                    )
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                    tool_names = [t.name for t in tools]
                    all_tools.extend(tools)

                    jl.log_step(
                        step_type="MCP_CONNECT",
                        title=client_cfg.name,
                        details={
                            "command": client_cfg.command,
                            "args": client_cfg.args,
                            "tools_loaded": tool_names,
                        },
                        success=True,
                    )
                    logger.info("[%s] Connected | tools: %s", client_cfg.name, tool_names)

                except Exception as exc:
                    tb = traceback.format_exc()
                    jl.log_step(
                        step_type="MCP_CONNECT",
                        title=client_cfg.name,
                        details={"command": client_cfg.command, "args": client_cfg.args},
                        error=f"{exc}\n{tb}",
                        success=False,
                    )
                    logger.error("[%s] Connection failed: %s", client_cfg.name, exc)

            if not all_tools:
                jl.log_step(
                    step_type="INFO",
                    title="No tools available",
                    details={"note": "Running with LLM only (no MCP tools configured or all failed to connect)."},
                )

            # ----------------------------------------------------------------
            # PHASE 2 — Build the ReAct agent
            # ----------------------------------------------------------------
            tool_descriptions = "\n".join(
                f"  - {t.name}: {getattr(t, 'description', 'no description')}"
                for t in all_tools
            )
            enriched_prompt = config.agent.system_prompt + (
                f"\n\nAvailable tools:\n{tool_descriptions}" if tool_descriptions else ""
            )

            llm = ChatOllama(
                model=config.model.model_name,
                temperature=config.model.temperature,
                base_url=config.model.base_url,
            )
            graph = create_react_agent(model=llm, tools=all_tools)

            jl.log_step(
                step_type="AGENT_INIT",
                title="LangGraph ReAct agent ready",
                details={
                    "model": config.model.model_name,
                    "temperature": config.model.temperature,
                    "tools": [t.name for t in all_tools],
                },
            )

            # ----------------------------------------------------------------
            # PHASE 3 — Run the ReAct loop + log every event
            # ----------------------------------------------------------------
            messages = [
                SystemMessage(content=enriched_prompt),
                HumanMessage(content=task),
            ]

            # Track which tool calls we've already logged (by tool call id)
            _logged_tool_calls: set = set()
            _llm_step = 0

            async for event in graph.astream(
                {"messages": messages},
                stream_mode="values",
            ):
                last_msg = event["messages"][-1]

                # ── AIMessage: LLM produced text or tool-call plan ────────
                if isinstance(last_msg, AIMessage):
                    tool_calls = getattr(last_msg, "tool_calls", []) or []

                    # Log the text part of the LLM response (if any)
                    if last_msg.content:
                        _llm_step += 1
                        jl.log_step(
                            step_type="LLM_RESPONSE",
                            title=f"LLM turn {_llm_step}",
                            output=_truncate(str(last_msg.content)),
                        )
                        final_answer = last_msg.content

                    # Log each tool call the LLM decided to make
                    for tc in tool_calls:
                        tc_id = tc.get("id", "")
                        if tc_id in _logged_tool_calls:
                            continue
                        _logged_tool_calls.add(tc_id)
                        jl.log_step(
                            step_type="TOOL_CALL",
                            title=tc.get("name", "unknown"),
                            details={
                                "tool": tc.get("name"),
                                "call_id": tc_id,
                                "input": _tool_input(tc),
                            },
                        )

                # ── ToolMessage: result came back from a tool ─────────────
                elif isinstance(last_msg, ToolMessage):
                    raw_content = last_msg.content or ""
                    # Detect error by checking for non-zero return codes or exception text
                    is_error = (
                        "error" in str(raw_content).lower()
                        or "exception" in str(raw_content).lower()
                        or "traceback" in str(raw_content).lower()
                    )
                    jl.log_step(
                        step_type="TOOL_RESULT",
                        title=getattr(last_msg, "name", "tool") or "tool",
                        details={"call_id": getattr(last_msg, "tool_call_id", "")},
                        output=_truncate(str(raw_content)),
                        success=not is_error,
                        error=str(raw_content) if is_error else None,
                    )

            # ── Done ──────────────────────────────────────────────────────
            success = True

    except Exception as exc:
        tb = traceback.format_exc()
        jl.log_step(
            step_type="FATAL_ERROR",
            title=type(exc).__name__,
            error=f"{exc}\n\n{tb}",
            success=False,
        )
        logger.exception("[%s] Job %s failed with unhandled exception", config.agent.name, jl.job_id)
        final_answer = f"ERROR: {exc}"
        success = False

    finally:
        jl.finish(final_answer=final_answer, success=success)
        logger.info(
            "[%s] Job %s %s | log: %s",
            config.agent.name,
            jl.job_id,
            "COMPLETE" if success else "FAILED",
            jl.path,
        )

    return final_answer or "Agent completed the task but produced no text output."
