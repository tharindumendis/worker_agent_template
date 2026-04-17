"""
core/config_loader.py
---------------------
Loads and validates config.yaml into typed dataclasses.
Import and use `load_config()` anywhere in the project.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Dataclass models
# ---------------------------------------------------------------------------


@dataclass
class ModelConfig:
    provider: str = "ollama"  # e.g., "ollama", "openai", "gemini", "anthropic", "bedrock"
    model_name: str = "llama3.2"
    temperature: float = 0.0
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = None


@dataclass
class MCPClientConfig:
    """Represents one external MCP server this worker connects to as a client."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict = field(default_factory=dict)  # optional extra env vars


@dataclass
class ServerConfig:
    name: str = "worker-agent-server"
    port: int = 8001
    transport: str = "stdio"  # "stdio" | "sse"
    host: str = "0.0.0.0"


DEFAULT_DESCRIPTION = (
    "Run the Worker Agent's internal ReAct loop to complete a sub-task.\n"
    "Args:\n"
    "    instruction: A clear, self-contained description of the task to perform.\n\n"
    "Returns:\n"
    "    The final result produced by the agent after it has finished reasoning\n"
    "    and using its tools. A log file path is appended for traceability."
)


@dataclass
class AgentConfig:
    name: str = "WorkerAgent"
    version: str = "1.0.0"
    description: str = DEFAULT_DESCRIPTION
    system_prompt: str = "You are a helpful worker agent."


@dataclass
class AppConfig:
    agent: AgentConfig = field(default_factory=AgentConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    mcp_clients: list[MCPClientConfig] = field(default_factory=list)
    server: ServerConfig = field(default_factory=ServerConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(config_path: str | None = None) -> AppConfig:
    """
    Priority:
    1. config_path (passed to function)
    2. WORKER_AGENT_CONFIG (environment variable)
    3. ./config.yaml (Current Working Directory)
    4. ../config.yaml (Package Root fallback)
    """

    # Define potential locations
    env_path = os.getenv("WORKER_AGENT_CONFIG")
    cwd_path = Path.cwd() / "config.yaml"
    package_root_path = Path(__file__).parent.parent / "config.yaml"

    # Select the first one that exists
    if config_path:
        final_path = Path(config_path)
    elif env_path:
        final_path = Path(env_path)
    elif cwd_path.exists():
        final_path = cwd_path
    else:
        final_path = package_root_path

    # Final check
    if not final_path.exists():
        raise FileNotFoundError(
            f"Config file not found. Checked:\n"
            f"- Explicit path: {config_path}\n"
            f"- Env Var (WORKER_AGENT_CONFIG): {env_path}\n"
            f"- Current Directory: {cwd_path}\n"
            f"- Package Fallback: {package_root_path}\n"
            f"Please ensure a 'config.yaml' exists in your current folder."
        )

    print(f"[*] Using config: {final_path.absolute()}")

    with open(final_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # --- Agent ---
    agent_raw = raw.get("agent", {})
    agent = AgentConfig(
        name=agent_raw.get("name", "WorkerAgent"),
        version=agent_raw.get("version", "1.0.0"),
        description=agent_raw.get("description", DEFAULT_DESCRIPTION),
        system_prompt=agent_raw.get("system_prompt", "You are a helpful worker agent."),
    )

    # --- Model ---
    model_raw = raw.get("model", {})
    model = ModelConfig(
        provider=model_raw.get("provider", "ollama"),
        model_name=model_raw.get("model_name", "llama3.2"),
        temperature=float(model_raw.get("temperature", 0.0)),
        base_url=model_raw.get("base_url", "http://localhost:11434"),
        api_key=model_raw.get("api_key", os.getenv("API_KEY")),
        aws_access_key_id=model_raw.get("aws_access_key_id"),
        aws_secret_access_key=model_raw.get("aws_secret_access_key"),
        aws_region=model_raw.get("aws_region"),
    )

    # --- MCP Clients ---
    mcp_clients = []
    for entry in raw.get("mcp_clients", []) or []:
        mcp_clients.append(
            MCPClientConfig(
                name=entry["name"],
                command=entry["command"],
                args=entry.get("args", []),
                env=entry.get("env", {}),
            )
        )

    # --- Server ---
    server_raw = raw.get("server", {})
    server = ServerConfig(
        name=server_raw.get("name", "worker-agent-server"),
        port=int(server_raw.get("port", 8001)),
        transport=server_raw.get("transport", "stdio"),
        host=server_raw.get("host", "0.0.0.0"),
    )

    return AppConfig(agent=agent, model=model, mcp_clients=mcp_clients, server=server)
