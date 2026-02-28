# 🤖 Universal Worker Agent Template

A **config-driven, plug-and-play worker agent** template.  
Clone the folder, edit `config.yaml`, and you have a brand new specialized agent — no code changes needed.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│               Main Agent                    │
│   (calls workers via MCP tool calls)        │
└───────────────────┬─────────────────────────┘
                    │ MCP (stdio / SSE)
          ┌─────────▼──────────┐
          │      main.py       │  ◄─── FastMCP bridge
          │  execute_task(...)  │       exposes 1 tool
          └─────────┬──────────┘
                    │ asyncio
          ┌─────────▼──────────┐
          │   core/agent.py    │  ◄─── LangGraph ReAct loop
          │  LangGraph + Ollama │
          └─────────┬──────────┘
                    │ MCP clients (stdio)
        ┌───────────┼───────────┐
   ┌────▼────┐  ┌───▼────┐  ┌──▼──────┐
   │FS Server│  │  Web   │  │ Custom  │
   │  (npx)  │  │ Search │  │ Server  │
   └─────────┘  └────────┘  └─────────┘
```

| Component     | File                    | Responsibility                                           |
| ------------- | ----------------------- | -------------------------------------------------------- |
| Config        | `config.yaml`           | Defines everything — identity, model, tools, server port |
| Config loader | `core/config_loader.py` | Parses YAML into typed dataclasses                       |
| ReAct Agent   | `core/agent.py`         | Loads MCP tools, runs LangGraph loop                     |
| MCP Bridge    | `main.py`               | Exposes `execute_task()` as an MCP server                |

---

## Quick Start

### 1. Install `uv` (if not already installed)

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install dependencies

```bash
uv sync
```

This creates a `.venv` and installs all dependencies from `pyproject.toml` automatically.

For development extras (ruff, mypy, pytest):

```bash
uv sync --all-extras
```

### 3. Configure your agent

Edit **`config.yaml`** — the only file you need to touch:

```yaml
agent:
  name: "FileMaster"
  description: "A specialized worker that organizes files and manages directory structures."
  system_prompt: "You are an expert at organizing and refactoring local files."

model:
  provider: "ollama" # Supported: "ollama", "openai", "gemini"
  model_name: "llama3.2" # any model loaded in Ollama
  # api_key: "your-api-key-here" # Uncomment if using openai or gemini (or set API_KEY env var)

mcp_clients:
  - name: "filesystem-server"
    command: "npx"
    args:
      ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/Dev/Project"]

server:
  transport: "stdio" # or "sse"
  port: 8001
```

### 4. Run as a subprocess (stdio) — standard MCP

```bash
uv run worker-agent
```

### 5. Run as an HTTP server (SSE) — call it from a browser or remote agent

```bash
uv run worker-agent --transport sse --port 8001
```

---

## Cloning a New Worker

1. Copy the whole folder:
   ```bash
   cp -r Agent_a Agent_researcher
   ```
2. Edit only `config.yaml` in the copy:
   - Change `agent.name`, `agent.description`, `agent.system_prompt`
   - Swap out `mcp_clients` for the tools this worker needs
   - Change `server.port` so it doesn't conflict
3. Install & run:
   ```bash
   cd Agent_researcher
   uv sync
   uv run worker-agent
   ```

---

## Example Worker Configs

### File Specialist

```yaml
agent:
  name: "FileMaster"
  description: "A specialized worker that organizes files and manages directory structures."
  system_prompt: "You are an expert at organizing and refactoring local files."
mcp_clients:
  - name: "filesystem-server"
    command: "npx"
    args:
      ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/Dev/Project"]
```

### Web Researcher

```yaml
agent:
  name: "SearchPro"
  description: "A research agent to summarize technical documentation found on the web."
  system_prompt: "You specialize in deep web research and summarizing technical docs."
model:
  provider: "openai"
  model_name: "gpt-4o-mini"
  api_key: "sk-..."
mcp_clients:
  - name: "brave-search"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-brave-search"]
```

### Local Python MCP Server

```yaml
mcp_clients:
  - name: "my-server"
    command: "python"
    args: ["D:/DEV/mcp/server.py"]
```

---

## How the Main Agent Calls This Worker

In your Main Agent's MCP config:

```json
{
  "mcpServers": {
    "file-worker": {
      "command": "uv",
      "args": ["--directory", "D:/DEV/mcp/Agent_a", "run", "worker-agent"]
    }
  }
}
```

### Dynamic Configuration (Multiple Workers)

If your Main Agent needs multiple specialized workers, you do not need to clone the entire repository multiple times. You can create several configuration YAML files (e.g., `web_worker.yaml`, `file_worker.yaml`) and pass them dynamically using the `WORKER_AGENT_CONFIG` environment variable.

```json
{
  "mcpServers": {
    "web-worker": {
      "command": "uv",
      "args": ["--directory", "D:/DEV/mcp/Agent_a", "run", "worker-agent"],
      "env": {
        "WORKER_AGENT_CONFIG": "D:/DEV/mcp/Agent_a/web_worker.yaml"
      }
    },
    "file-worker": {
      "command": "uv",
      "args": ["--directory", "D:/DEV/mcp/Agent_a", "run", "worker-agent"],
      "env": {
        "WORKER_AGENT_CONFIG": "D:/DEV/mcp/Agent_a/file_worker.yaml"
      }
    }
  }
}
```

Or run it directly with `uvx` and an environment variable if the package is published:

```bash
# Linux/macOS
WORKER_AGENT_CONFIG="./custom_config.yaml" uvx worker-agent

# Windows (PowerShell)
$env:WORKER_AGENT_CONFIG="./custom_config.yaml"; uvx worker-agent
```

The worker exposes one tool:

- **`execute_task(instruction: str) → str`**

The Main Agent calls it like any other MCP tool. The worker handles reasoning, tool use, and error recovery internally, returning only the final result.

---

## Project Structure

```
Agent_a/
├── config.yaml           ← The only file you edit per clone
├── main.py               ← MCP bridge (FastMCP)
├── pyproject.toml         ← All deps & build config (hatchling)
├── README.md
└── core/
    ├── __init__.py
    ├── agent.py          ← LangGraph ReAct loop
    └── config_loader.py  ← YAML → typed dataclasses
```

---

## Development Commands

```bash
# Install in dev mode with all extras
uv sync --all-extras

# Run from the project directory
uv run worker-agent
uv run worker-agent --transport sse --port 8001

