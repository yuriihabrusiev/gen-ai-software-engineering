# AGENTS.md — Transaction Processing Pipeline (Starter)

## Purpose

This file guides an AI coding agent implementing the pipeline described in
`specification.md`. It is a **starter** — no pipeline code exists yet, and
`specification.md` itself has not been written. The `spec-writer` subagent
(via the `/write-spec` skill) must extend this file with project-specific rules
once the spec exists. Where this file and `specification.md` disagree,
`specification.md` is authoritative — this file restates the parts an agent must
never violate while writing code.

## Assumed Tech Stack

| Layer | Assumption | Notes |
|---|---|---|
| Language / runtime | Python 3.12+ | Chosen for continuity with this course's stack and `decimal.Decimal` support. |
| Pipeline stages | Plain Python modules under `pipeline/` | No web framework required for the pipeline itself — stages are file-in/file-out. |
| Front-end | Static HTML/CSS/JS dashboard under `frontend/` | Served by a minimal Python HTTP server; polls `shared/results/` for status. No build step. |
| Custom MCP server | FastMCP (`mcp/server.py`) | Exposes `get_transaction_status`, `list_pipeline_results`, and the `pipeline://summary` resource. |
| Test runner | pytest + pytest-cov | Coverage gate (see `.claude/settings.json`) blocks `git push` below 80%. |
| Tooling | `pip` / `venv` | Keep dependencies in `requirements.txt`. |

## Domain Rules (non-negotiable)

- Money is always parsed and compared as `decimal.Decimal`, never `float`. Amounts
  arrive as strings in `sample-transactions.json` and in every inter-stage message.
- Currency codes are validated against ISO 4217. An unknown code is a validation
  rejection, not a crash.
- Stages communicate only through the file-based protocol in `shared/{input,
  processing,output,results}/`, using the standard message envelope (`message_id`,
  `timestamp`, `source_stage`, `target_stage`, `message_type`, `data`). No stage
  calls another stage's code directly.
- Every stage writes a structured audit-trail log entry (ISO 8601 UTC timestamp,
  stage name, `transaction_id`, outcome) for every record it processes, pass or
  reject.
- `source_account`, `destination_account`, and any free-text `description` field are
  sensitive. Never write them to logs in plaintext.

## Code Style

- snake_case for identifiers; one module per pipeline stage under `pipeline/`.
- Each stage exposes a single pure-ish entry point of the shape
  `process_transaction(record: dict) -> dict`, returning the (possibly rejected)
  record — no stage mutates global state or another stage's files directly.
- Rejections are explicit: a stage returns/writes a `status` field and a
  human-readable `reason`, never raises an uncaught exception for a business-rule
  rejection (exceptions are reserved for genuine bugs/IO failures).

## Testing & Verification Expectations

- Every pipeline stage gets unit tests covering: the happy path, at least one
  rejection path, and any boundary the stage introduces (e.g. the $10,000 fraud
  threshold, an unknown currency code).
- One integration test runs the full orchestrator over a small fixture set and
  asserts every input record has a corresponding file in `shared/results/`.
- Tests must not touch the real `shared/` directories — use a temp directory
  (`tmp_path` fixture or equivalent) so test runs never pollute or depend on a real
  pipeline run.
- Coverage gate is enforced by a hook (`.claude/hooks/check-coverage.sh`) that
  blocks `git push` below 80%; target 90%+.

## Security & Compliance Constraints

- Never log a full account number or free-text description at any log level.
- Treat context7 lookups and any MCP tool calls as read-only research/status
  actions — they must never be the only path that produces a pipeline result file.
- The custom MCP server (`mcp/server.py`) only reads from `shared/results/`; it
  never writes to or mutates pipeline state.

## Edge Case Handling Directives

- When a signal is ambiguous (e.g. borderline risk score, malformed but
  plausible amount), **prefer the fail-safe direction**: reject/flag rather than
  silently pass. A false-positive rejection is recoverable by review; a
  false-negative fraud pass may not be.
- A negative amount (see `TXN007`, a refund) is not automatically invalid — confirm
  in `specification.md` whether refunds are a distinct `transaction_type` with its
  own sign convention before rejecting on sign alone.
- Never let one malformed record crash the orchestrator run for the rest of the
  batch — isolate per-record failures and record them as a rejection outcome.

## Adding New Features

1. Add or update the relevant Mid-Level Objective in `specification.md` first.
2. Write the Low-Level Task (exact `Task:` / `Prompt:` / `File to CREATE:` /
   `Function to CREATE:` / `Details:` block) before writing code.
3. Confirm the new stage/feature uses the existing file-based message envelope and
   audit-logging path rather than a parallel implementation.
4. Add or update tests for the new behavior; re-run the coverage gate locally
   before pushing.
