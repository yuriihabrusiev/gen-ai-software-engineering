# Homework 5: Configure MCP Servers

> **Student Name**: Yurii Habrusiev
> **Date Submitted**: July 5, 2026
> **AI Tools Used**: Claude Code

---

## Project Overview

This project configures four MCP (Model Context Protocol) servers so Claude can interact with
GitHub, the local filesystem, Jira/Notion, and a custom FastMCP server built for this homework.
See `TASKS.md` for the full task breakdown.

## Task 4: Custom MCP Server with FastMCP

`custom-mcp-server/` is a standalone, `uv`-managed Python project built with
[FastMCP](https://gofastmcp.com/). It serves lorem-ipsum text two ways:

- **Resource** (`lorem://lorem-ipsum`, `lorem://lorem-ipsum/{word_count}`) — a URI Claude can
  *read* from, like a file or an API response.
- **Tool** (`read(word_count: int = 30)`) — an action Claude can *call* to perform an operation.

Both are backed by the same `get_lorem_words()` helper in `server.py`, which reads
`lorem-ipsum.md` and returns exactly `word_count` words (capped at however many the file has, no
crash on over-requests). FastMCP was chosen because it lets a server be defined as plain Python
functions with decorators (`@mcp.resource`, `@mcp.tool`), with no protocol boilerplate.

See [HOWTORUN.md](HOWTORUN.md) for install, run, MCP-connection, and testing instructions.

## Project Structure

```text
homework-5/
├── README.md                          (this file)
├── HOWTORUN.md                        (install, run, connect, and usage instructions)
├── TASKS.md                           (homework task breakdown)
├── .mcp.json                          (MCP server configuration, custom-mcp-server registered)
├── custom-mcp-server/
│   ├── server.py                      (FastMCP server: Resource + read Tool)
│   ├── lorem-ipsum.md                 (source text for resource/tool output)
│   ├── pyproject.toml                 (fastmcp dependency)
│   ├── mise.toml                      (setup/dev/run/lint/typecheck tasks)
│   └── README.md
└── docs/
    └── screenshots/                   (MCP call result screenshots)
```

*This project was completed as part of the AI-Assisted Development course.*
