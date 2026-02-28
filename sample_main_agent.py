# -*- coding: utf-8 -*-
"""
main_agent.py — Main Agent (Test Client)
-----------------------------------------
Spawns the Worker Agent (main.py) as an MCP subprocess,
discovers its `execute_task` tool dynamically, and drives
it through a LangGraph ReAct loop.

Usage:
    python sample_main_agent.py
    python sample_main_agent.py --task "List all .py files in D:/DEV/mcp/Agent_a"
    python sample_main_agent.py --model qwen3-coder:480b-cloud
    python sample_main_agent.py --config "D:/DEV/mcp/Agent_a/file_worker.yaml"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Force UTF-8 output on Windows so emoji/unicode don't crash
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

# ---------------------------------------------------------------------------
# Logging  (stderr so it doesn't pollute tool output)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    stream=sys.stderr,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKER_PYTHON = str(Path(__file__).parent / ".venv" / "Scripts" / "python.exe")
WORKER_SCRIPT = str(Path(__file__).parent / "main.py")

MAIN_AGENT_SYSTEM_PROMPT = """\
You are the Main Agent — an orchestrator that delegates complex sub-tasks to specialist Worker Agents.

You have access to one tool:
  - execute_task(instruction): Sends a precise instruction to a Worker Agent and returns its result.

Your job:
1. Understand the user's high-level goal.
2. Break it into clear, atomic sub-tasks if needed.
3. Call execute_task for each sub-task with a detailed, self-contained instruction.
4. Synthesize the results into a final answer for the user.

Be concise. Delegate aggressively — don't try to solve tasks yourself when a worker can do it.
"""

# ---------------------------------------------------------------------------
# Pretty printer for agent events
# ---------------------------------------------------------------------------

def _print_event(event: dict) -> None:
    messages = event.get("messages", [])
    if not messages:
        return
    last = messages[-1]

    if isinstance(last, AIMessage):
        if last.content:
            print(f"\n[Agent] \033[96mMain Agent:\033[0m {last.content}")
        if hasattr(last, "tool_calls") and last.tool_calls:
            for tc in last.tool_calls:
                args = tc.get("args", {})
                instruction = args.get("instruction", "")
                print(f"\n[Tool] \033[93mCalling Worker -> execute_task:\033[0m")
                print(f"   \033[90m{instruction[:300]}{'...' if len(instruction) > 300 else ''}\033[0m")

    elif isinstance(last, ToolMessage):
        content = last.content or ""
        print(f"\n[Result] \033[92mWorker Result:\033[0m")
        # Indent the result for readability
        for line in str(content).splitlines():
            print(f"   {line}")


# ---------------------------------------------------------------------------
# Core async runner
# ---------------------------------------------------------------------------

async def run_main_agent(task: str, model_name: str, config_path: str | None = None) -> str:
    """
    1. Spawn Worker Agent as MCP subprocess.
    2. Discover its tools (execute_task).
    3. Run Main Agent's ReAct loop.
    4. Return final answer.
    """
    print(f"\n\033[90m[*] Spawning Worker Agent subprocess...\033[0m")

    # Set up environment variables to pass the custom config
    env = os.environ.copy()
    if config_path:
        abs_config = str(Path(config_path).absolute())
        env["WORKER_AGENT_CONFIG"] = abs_config
        print(f"\033[90m[*] Passing dynamically configured config: {abs_config}\033[0m")

    worker_params = StdioServerParameters(
        command=WORKER_PYTHON,
        args=[WORKER_SCRIPT],
        env=env,
    )

    async with stdio_client(worker_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover tools the worker exposes
            tools = await load_mcp_tools(session)
            tool_names = [t.name for t in tools]
            print(f"\033[90m[*] Discovered tools: {tool_names}\033[0m")

            if not tools:
                return "[ERROR] Worker Agent exposed no tools. Check that main.py is running correctly."

            # Build Main Agent's LLM + ReAct graph
            llm = ChatOllama(
                model=model_name,
                temperature=0.0,
                base_url="http://localhost:11434",
            )
            graph = create_react_agent(model=llm, tools=tools)

            messages = [
                SystemMessage(content=MAIN_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=task),
            ]

            print(f"\n\033[1m[Task]\033[0m {task}\n")
            print("-" * 60)

            final_answer = ""
            async for event in graph.astream(
                {"messages": messages},
                stream_mode="values",
            ):
                _print_event(event)
                last = event["messages"][-1]
                if hasattr(last, "content") and last.content:
                    final_answer = last.content

            return final_answer


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

async def interactive_loop(model_name: str, config_path: str | None = None) -> None:
    print("\n" + "=" * 60)
    print("  [Main Agent] <-> [Worker Agent]  (MCP)  |  Test Console")
    print("=" * 60)
    print(f"  Model : {model_name}")
    print(f"  Worker: {WORKER_SCRIPT}")
    print("  Type your task below. 'quit' or Ctrl-C to exit.\n")

    while True:
        try:
            task = input("\n>> Task: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nExiting.")
            break

        if not task:
            continue
        if task.lower() in {"quit", "exit", "q"}:
            print("Exiting.")
            break

        try:
            result = await run_main_agent(task, model_name, config_path)
            print("\n" + "-" * 60)
            print(f"\n[OK] \033[1mFinal Answer:\033[0m\n{result}")
            print("-" * 60)
        except Exception as exc:
            print(f"\n[ERROR] \033[31m{exc}\033[0m")
            logging.exception("run_main_agent failed")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Main Agent — orchestrates the Worker Agent via MCP for testing."
    )
    p.add_argument(
        "--task", "-t",
        type=str,
        default=None,
        help="Run a single task non-interactively and exit.",
    )
    p.add_argument(
        "--model", "-m",
        type=str,
        default="qwen3-coder:480b-cloud",
        help="Ollama model name for the Main Agent (default: qwen3-coder:480b-cloud)",
    )
    p.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to a custom config.yaml file to pass to the Worker Agent",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.task:
        # Single-shot non-interactive mode
        result = asyncio.run(run_main_agent(args.task, args.model, args.config))
        print("\n" + "-" * 60)
        print(f"\n[OK] Final Answer:\n{result}")
    else:
        # Interactive REPL
        asyncio.run(interactive_loop(args.model, args.config))
