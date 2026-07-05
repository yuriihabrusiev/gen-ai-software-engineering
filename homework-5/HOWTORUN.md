# HOWTORUN

## Custom MCP Server (`custom-mcp-server/`)

A FastMCP server exposing lorem-ipsum text via a **Resource** and a **Tool**.

### Concepts: Resources vs Tools

- **Resources** are URIs Claude can *read* from, like a file or an API response. They're addressed
  by URI and return content, not a result of an action. This server exposes:
  - `lorem://lorem-ipsum` — the first 30 words of `lorem-ipsum.md`.
  - `lorem://lorem-ipsum/{word_count}` — a templated URI returning the first `word_count` words.
- **Tools** are actions Claude can *call* to perform an operation (reading a file, running a
  command, hitting an API). This server exposes:
  - `read(word_count: int = 30)` — returns the first `word_count` words of `lorem-ipsum.md`.

  Both share the same `get_lorem_words()` helper in `server.py`, so the Resource and Tool always
  return identical content for the same `word_count`.

### 1. Install dependencies

```bash
cd custom-mcp-server
uv sync
# or: mise run setup
```

This installs `fastmcp` (and dev tools `ruff`/`ty`) into `custom-mcp-server/.venv`.

### 2. Run the server

```bash
cd custom-mcp-server
uv run server.py
# or: mise run dev   /   mise run run
```

The server starts over stdio — it's meant to be launched by an MCP client (Claude Code, Copilot,
MCP Inspector), not used standalone in a terminal.

### 3. Connect the MCP configuration

`homework-5/.mcp.json` registers the server for Claude Code / Copilot:

```json
{
  "mcpServers": {
    "custom-mcp-server": {
      "command": "uv",
      "args": ["run", "--directory", "custom-mcp-server", "server.py"]
    }
  }
}
```

Open the `homework-5/` folder in Claude Code and run `claude mcp list` — `custom-mcp-server` should
appear (approve it once if prompted; project-scoped servers require a one-time trust confirmation).

### 4. Use / test the `read` tool

From a Claude Code session in `homework-5/`, prompt:

> Use the read tool from custom-mcp-server to get 50 words of lorem ipsum.

Claude will call `read(word_count=50)` and return exactly 50 words.

To test without a full client, use the FastMCP CLI or an in-memory `Client`:

```bash
cd custom-mcp-server
uv run python -c "
import asyncio
from fastmcp import Client
from server import mcp

async def main():
    async with Client(mcp) as client:
        result = await client.call_tool('read', {'word_count': 50})
        print(result.data)

asyncio.run(main())
"
```

You can also inspect the server interactively with the MCP Inspector:

```bash
cd custom-mcp-server
uv run fastmcp dev inspector server.py
```
