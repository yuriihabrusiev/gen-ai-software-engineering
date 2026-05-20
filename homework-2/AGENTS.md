# AGENTS.md — Customer Support Ticket API

## Project Overview

A FastAPI-based customer support ticket management system with multi-format import (CSV, JSON, XML) and SQLite persistence. Built as Homework 2 for the Gen AI Software Engineering course.

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.14 | Runtime |
| FastAPI | Web framework |
| SQLite (`sqlite3`) | Persistence |
| Pydantic v2 | Data validation |
| uvicorn | ASGI server |
| ruff | Linter |
| ty | Type checker |
| uv | Package manager |
| mise | Tool version manager |

## Project Structure

```
homework-2/
├── src/
│   ├── main.py                   # FastAPI app + lifespan (DB init)
│   ├── database.py               # SQLite DDL, connection context manager
│   ├── models/
│   │   └── ticket.py             # Pydantic models, enums, import summary
│   ├── routers/
│   │   └── tickets.py            # All /tickets route handlers
│   └── services/
│       ├── ticket_service.py     # CRUD business logic against SQLite
│       └── import_service.py     # CSV / JSON / XML parsers
├── mise.toml                     # Tool versions + task definitions
├── pyproject.toml                # uv project config + ruff settings
├── TASKS.md                      # Assignment requirements
└── AGENTS.md                     # This file
```

## Common Commands

```bash
# Start dev server (hot reload)
mise run dev

# Lint + format check + type check
mise run lint

# Lint + format check + type check (with auto-fix)
mise run lint:fix

# Run any uv command
mise exec -- uv run <command>
```

## Before Committing

Always run the following before committing changes:

```bash
mise run lint:fix   # auto-fix lint issues and apply formatting
mise run lint       # final check — must pass with zero errors
```

`lint` runs three checks in sequence:
1. `ruff check src/` — linting
2. `ruff format --check src/` — formatting (fails if files need reformatting)
3. `ty check src/` — static type checking

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tickets` | Create a ticket (201) |
| `GET` | `/tickets` | List tickets — filter via `?status=`, `?category=`, `?priority=` |
| `GET` | `/tickets/{id}` | Get ticket by ID (404 if missing) |
| `PUT` | `/tickets/{id}` | Partial update (404 if missing) |
| `DELETE` | `/tickets/{id}` | Delete ticket (204, 404 if missing) |
| `POST` | `/tickets/import` | Bulk import from CSV / JSON / XML file |

Interactive docs available at `http://localhost:8000/docs` when the dev server is running.

## Ticket Model

Key fields and allowed values:

- **category**: `account_access` | `technical_issue` | `billing_question` | `feature_request` | `bug_report` | `other`
- **priority**: `urgent` | `high` | `medium` | `low`
- **status**: `new` | `in_progress` | `waiting_customer` | `resolved` | `closed`
- **metadata.source**: `web_form` | `email` | `api` | `chat` | `phone`

## Bulk Import

Send a multipart `file` field to `POST /tickets/import`. Accepted formats:

- **CSV** — first row is the header; columns match ticket fields; `tags` can be comma-separated string
- **JSON** — root must be an array of ticket objects
- **XML** — root element wraps `<ticket>` children; tags use nested `<tags><tag>…</tag></tags>`

Response always includes `{ total, successful, failed, errors[] }` — partial success is allowed.

## Conventions

- All enums use `StrEnum` (Python 3.11+) for clean JSON serialisation.
- `tags` and `metadata` are stored as JSON strings in SQLite, deserialised on read.
- `updated_at` is automatically set on every PUT. `resolved_at` is set when `status` transitions to `resolved`.
- HTTP status codes: 201 (create), 204 (delete), 400 (bad file), 404 (not found), 415 (unsupported format), 422 (validation error).

## Adding New Features

1. Add or extend models in `src/models/ticket.py`.
2. Add business logic to `src/services/ticket_service.py`.
3. Add route handler in `src/routers/tickets.py`.
4. If schema changes, update `DDL` in `src/database.py` and delete `tickets.db` to recreate.
5. Run `mise run lint:fix` then `mise run lint` before committing.
