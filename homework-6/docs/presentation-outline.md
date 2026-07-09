# Presentation Outline — Transaction Processing Pipeline Capstone

Author: Yurii Habrusiev

> This is the content for `docs/presentation.pdf`. It is written as one section
> per slide. A human still needs to export this to an actual PDF (e.g. paste
> into Google Slides/Keynote/Markdown-to-PDF tooling) and save it at
> `docs/presentation.pdf`, then link it in the PR description — this agent
> cannot generate the PDF file itself.

---

## Slide 1 — Title

- Transaction Processing Pipeline
- A four-agent capstone: Specification -> Code Generation -> Unit Tests -> Documentation
- Author: Yurii Habrusiev

---

## Slide 2 — Problem & Objective

- Goal: validate, risk-score, and compliance-screen every transaction in
  `sample-transactions.json` (8 sample records), producing one auditable
  outcome per transaction (`REJECTED` / `CLEARED` / `HELD_FOR_REVIEW`).
- Non-negotiable domain rules: money is always `decimal.Decimal` (never
  `float`), currency validated against an offline ISO 4217 allow-list, no
  sensitive fields (`source_account`, `destination_account`, `description`)
  ever hit a log or console in plaintext.

---

## Slide 3 — Four-Agent Pipeline (Meta Level)

- Agent 1 (`spec-writer`): wrote `specification.md` + `agents.md` from
  `TASKS.md`.
- Agent 2 (`pipeline-builder`): built `orchestrator.py`, `pipeline/*.py`,
  `frontend/`, `mcp/server.py`, `.mcp.json`, logged >= 2 context7 queries in
  `research-notes.md`.
- Agent 3 (`test-writer`): built `tests/` — 69 tests, 99% coverage on
  `pipeline/` + `mcp/`.
- Agent 4 (`docs-writer`, this agent): `README.md`, `HOWTORUN.md`, this
  presentation outline.

---

## Slide 4 — Architecture Overview

```
orchestrator.py -> shared/input/ -> Validation -> shared/output/->processing/
   -> Fraud Detection -> shared/output/->processing/ -> Compliance Check
   -> shared/results/ (terminal records + summary.json + audit_log.jsonl)
   -> consumed independently by frontend/ (static dashboard) and
      mcp/server.py ("pipeline-status" MCP server)
```

- Stages never call each other's code directly — everything is a file move
  through `shared/{input,processing,output,results}/` using a standard
  message envelope (`message_id`, `timestamp`, `source_stage`,
  `target_stage`, `message_type`, `data`).
- Per-record isolation: one malformed record cannot crash the batch — the
  orchestrator catches per-stage exceptions and writes a `REJECTED` /
  `INTERNAL_ERROR` terminal record instead.

---

## Slide 5 — Stage 1: Validation (`pipeline/validator.py`)

- Confirms all 9 required fields are present (`MISSING_REQUIRED_FIELD`).
- Parses `amount` as `Decimal(str(...))` (`INVALID_AMOUNT_FORMAT` on failure).
- Enforces sign convention by `transaction_type`: `transfer`/`wire_transfer`
  must be positive (`NON_POSITIVE_AMOUNT`); `refund` must be negative
  (`REFUND_MUST_BE_NEGATIVE`).
- Validates `currency` against a fixed, offline 40-code ISO 4217 set
  (`CURRENCY_NOT_ISO4217`) — no network calls.
- Rejects terminate immediately (written straight to `shared/results/`);
  everything else is forwarded, normalized, to Fraud Detection.

---

## Slide 6 — Stage 2: Fraud Detection (`pipeline/fraud_detector.py`)

- Never rejects on its own — only scores and annotates.
- Additive risk score (capped at 100): amount tier on `abs(amount)`
  (+60 / +40 / +15, mutually exclusive), off-hours UTC timestamp
  (`< 6` or `>= 22`, +20), cross-border destination (`metadata.country`
  outside `{"US"}`, +15, fails safe to cross-border if missing/unknown),
  wire-transfer channel (+10).
- Risk level: `LOW` (< 30) / `MEDIUM` (30-59) / `HIGH` (>= 60);
  `fraud_status` is `flagged` for anything not `LOW`.
- Always forwards to Compliance Check — the final decision is not made here.

---

## Slide 7 — Stage 3: Compliance Check (`pipeline/compliance_checker.py`)

- Terminal stage for every record that survived Validation.
- Watchlist screen on `source_account`/`destination_account` against a static
  set (`WATCHLIST_ACCOUNTS = {"ACC-9999"}`) — a hit overrides the fraud score
  entirely -> `HELD_FOR_REVIEW` / `WATCHLIST_MATCH`, with the account masked
  (`ACC-***99`) in the human-facing note.
- Otherwise, anything the fraud stage flagged -> `HELD_FOR_REVIEW` /
  `FRAUD_RISK_FLAGGED`.
- Everything else -> `CLEARED`.
- Writes exactly one terminal record to `shared/results/<transaction_id>.json`.

---

## Slide 8 — Demo Flow

0. Or skip setup entirely: open the **live hosted demo** at
   https://transaction-pipeline-demo.onrender.com/frontend/ (Render free
   tier — may take ~30-60s to wake up) and click "Run Pipeline".
1. `mise install && mise run setup` (`uv sync` under the hood) — Python 3.14
   via `mise`, dependencies via `uv`/`pyproject.toml`, no `pip`/`venv` step.
2. `mise run pipeline` (`uv run python orchestrator.py`) — process all 8
   sample transactions; show the printed summary (3 `CLEARED`, 4
   `HELD_FOR_REVIEW`, 1 `REJECTED`).
3. `mise run dashboard` (`uv run python -m http.server 8000`) from repo
   root, open `http://localhost:8000/frontend/` — show the live dashboard
   reading `shared/results/`.
4. `mise run test` (`uv run pytest --cov=pipeline --cov=mcp
   --cov-report=term-missing`) — show 69 passed, 99% coverage. `mise run
   lint` / `mise run typecheck` (`ruff` / `ty`) both clean.
5. Open this repo in an MCP-aware client (`.mcp.json` auto-starts
   `context7` and `pipeline-status` via `uv run`) and call
   `get_transaction_status`, `list_pipeline_results`, and read the
   `pipeline://summary` resource live.
6. (Optional) Trigger the coverage-gate hook by attempting `git push` and
   showing it pass at 99% coverage.

---

## Slide 9 — Security & Compliance by Design

- `Decimal`-only money path — no `float` anywhere on amount comparisons or
  scoring math.
- Offline, deterministic currency and watchlist checks — no runtime network
  dependency for compliance-critical logic.
- PII discipline enforced at multiple layers: `pipeline/common.py`'s
  `append_audit_log` only accepts `(stage, transaction_id, outcome)` by
  construction; `mcp/server.py` strips `source_account`/`destination_account`/
  `description` from every tool response; `frontend/app.js` never renders
  those fields either.

---

## Slide 10 — Lessons Learned

- A strict file-based, envelope-driven inter-stage protocol (vs. direct
  function calls) made per-record failure isolation and independent testing
  of each stage straightforward, at the cost of more orchestration
  bookkeeping (`shared/processing/` hand-offs) in `orchestrator.py`.
- Writing the domain rules (Decimal-only, offline ISO 4217, PII masking) into
  `agents.md`/`specification.md` up front, before code generation, meant the
  generated pipeline code needed very little rework in the test-writing
  phase — most edge cases (e.g. `TXN003`'s watchlist hold overriding its low
  fraud score) were already anticipated by the spec's Mid-Level Objectives.
- Keeping the front-end and MCP server strictly read-only consumers of
  `shared/results/` (never triggering or mutating a pipeline run) simplified
  reasoning about the system's data flow and kept both surfaces trivially
  safe to demo.

---

## Slide 11 — Q&A / Links

- **Live demo**: https://transaction-pipeline-demo.onrender.com/frontend/
- `README.md` — architecture, stage responsibilities, tech stack.
- `HOWTORUN.md` — exact commands for setup, pipeline run, dashboard, tests, MCP.
- `specification.md` / `agents.md` — full technical spec and domain rules.
- `research-notes.md` — context7 queries made during Task 2/4.
