"""
main.py — The MCP Bridge
------------------------
Wraps the Worker Agent as an MCP server.

The outer "Main Agent" (or any MCP client) calls:
    execute_task(instruction="...")

This triggers the internal LangGraph ReAct loop, which:
  - connects to the MCP tool servers configured in config.yaml
  - reasons and acts until the sub-task is done
  - returns the final result as a plain string

Usage:
    # stdio transport (for use as subprocess by a parent MCP client):
    python main.py

    # SSE transport (for use over HTTP):
    python main.py --transport sse
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from mcp.server.fastmcp import FastMCP, Context

from core.agent import run_agent
from core.config_loader import load_config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load config once at startup
# ---------------------------------------------------------------------------
config = load_config()

# ---------------------------------------------------------------------------
# FastMCP server setup
# ---------------------------------------------------------------------------
mcp = FastMCP(config.server.name)


# ---------------------------------------------------------------------------
# Tool: execute_task
# ---------------------------------------------------------------------------
@mcp.tool(description=config.agent.description)
async def execute_task(ctx :Context ,instruction: str) -> str:
    """
    Args:
        instruction: A clear, self-contained description of the task to perform.

    Returns:
        The final result produced by the agent after it has finished reasoning
        and using its tools. A log file path is appended for traceability.
    """
    from core.job_logger import LOGS_DIR
    logger.info("Received task: %s", instruction[:200])
    try:
        await ctx.info(f"Executing task: {instruction[:200]}...")
        result = await run_agent(task=instruction, config=config)
        logger.info("Task finished successfully.")
        return result
    except Exception as exc:
        logger.exception("Agent failed with error: %s", exc)
        await ctx.error(f"Agent failed with error: {exc}")
        return f"ERROR: The agent encountered an unhandled exception: {exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Worker Agent MCP Server — {config.agent.name}")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=config.server.transport,
        help="Transport mode (stdio for subprocess, sse for HTTP). Default: from config.yaml",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.server.port,
        help=f"Port for SSE transport (default: {config.server.port})",
    )
    parser.add_argument(
        "--host",
        default=config.server.host,
        help=f"Host for SSE transport (default: {config.server.host})",
    )
    return parser.parse_args()


def _cli_entry() -> None:
    """
    Console-script entry point installed by setup.py / pyproject.toml.

    After ``pip install -e .`` (or a regular install) you can start the
    worker agent from any shell with::

        worker-agent                          # stdio transport (default)
        worker-agent --transport sse          # HTTP/SSE transport
        worker-agent --transport sse --port 9000 --host 127.0.0.1
    """
    args = parse_args()

    logger.info(
        "Starting '%s' (v%s) | transport=%s",
        config.agent.name,
        config.agent.version,
        args.transport,
    )

    if args.transport == "sse":
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    _cli_entry()
