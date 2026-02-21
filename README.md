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

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your agent

Edit **`config.yaml`** — the only file you need to touch:

```yaml
agent:
  name: "FileMaster"
  system_prompt: "You are an expert at organizing and refactoring local files."

model:
  model_name: "llama3.2" # any model loaded in Ollama

mcp_clients:
  - name: "filesystem-server"
    command: "npx"
    args:
      ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/Dev/Project"]

server:
  transport: "stdio" # or "sse"
  port: 8001
```

### 3. Run as a subprocess (stdio) — standard MCP

```bash
python main.py
```

### 4. Run as an HTTP server (SSE) — call it from a browser or remote agent

```bash
python main.py --transport sse --port 8001
```

---

## Cloning a New Worker

1. Copy the whole folder:
   ```bash
   cp -r Agent_a Agent_researcher
   ```
2. Edit only `config.yaml` in the copy:
   - Change `agent.name`, `agent.system_prompt`
   - Swap out `mcp_clients` for the tools this worker needs
   - Change `server.port` so it doesn't conflict
3. Run it: `python main.py`

---

## Example Worker Configs

### File Specialist

```yaml
agent:
  name: "FileMaster"
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
  system_prompt: "You specialize in deep web research and summarizing technical docs."
model:
  model_name: "mistral"
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
      "command": "python",
      "args": ["D:/DEV/mcp/Agent_a/main.py"]
    }
  }
}
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
├── requirements.txt
├── README.md
└── core/
    ├── __init__.py
    ├── agent.py          ← LangGraph ReAct loop
    └── config_loader.py  ← YAML → typed dataclasses
```

# Install in editable / dev mode (recommended while developing)
pip install -e ".[dev]"

# Run from anywhere after install
worker-agent
worker-agent --transport sse --port 8001

# Build a distributable wheel + sdist
pip install build
python -m build

# Publish to PyPI
pip install twine
twine upload dist/*
