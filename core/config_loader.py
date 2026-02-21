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
from typing import List, Optional

import yaml


# ---------------------------------------------------------------------------
# Dataclass models
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    provider: str = "ollama"
    model_name: str = "llama3.2"
    temperature: float = 0.0
    base_url: str = "http://localhost:11434"


@dataclass
class MCPClientConfig:
    """Represents one external MCP server this worker connects to as a client."""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: dict = field(default_factory=dict)   # optional extra env vars


@dataclass
class ServerConfig:
    name: str = "worker-agent-server"
    port: int = 8001
    transport: str = "stdio"   # "stdio" | "sse"
    host: str = "0.0.0.0"


@dataclass
class AgentConfig:
    name: str = "WorkerAgent"
    version: str = "1.0.0"
    system_prompt: str = "You are a helpful worker agent."


@dataclass
class AppConfig:
    agent: AgentConfig = field(default_factory=AgentConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    mcp_clients: List[MCPClientConfig] = field(default_factory=list)
    server: ServerConfig = field(default_factory=ServerConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load config.yaml from `config_path` (defaults to <project_root>/config.yaml).
    Returns a fully populated AppConfig dataclass.
    """
    if config_path is None:
        # Walk up from this file to find config.yaml at project root
        root = Path(__file__).parent.parent
        config_path = root / "config.yaml"

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at '{config_path}'. "
            "Copy config.yaml to the project root and customize it."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # --- Agent ---
    agent_raw = raw.get("agent", {})
    agent = AgentConfig(
        name=agent_raw.get("name", "WorkerAgent"),
        version=agent_raw.get("version", "1.0.0"),
        system_prompt=agent_raw.get("system_prompt", "You are a helpful worker agent."),
    )

    # --- Model ---
    model_raw = raw.get("model", {})
    model = ModelConfig(
        provider=model_raw.get("provider", "ollama"),
        model_name=model_raw.get("model_name", "llama3.2"),
        temperature=float(model_raw.get("temperature", 0.0)),
        base_url=model_raw.get("base_url", "http://localhost:11434"),
    )

    # --- MCP Clients ---
    mcp_clients = []
    for entry in raw.get("mcp_clients", []) or []:
        mcp_clients.append(MCPClientConfig(
            name=entry["name"],
            command=entry["command"],
            args=entry.get("args", []),
            env=entry.get("env", {}),
        ))

    # --- Server ---
    server_raw = raw.get("server", {})
    server = ServerConfig(
        name=server_raw.get("name", "worker-agent-server"),
        port=int(server_raw.get("port", 8001)),
        transport=server_raw.get("transport", "stdio"),
        host=server_raw.get("host", "0.0.0.0"),
    )

    return AppConfig(agent=agent, model=model, mcp_clients=mcp_clients, server=server)
