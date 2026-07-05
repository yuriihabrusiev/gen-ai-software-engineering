# Transaction Processing Pipeline

Created by **Yurii Habrusiev**

## What this is

This project is a file-based, three-stage transaction processing pipeline built
as a four-agent capstone (Specification -> Code Generation -> Unit Tests ->
Documentation). Per `specification.md`'s High-Level Objective, it validates,
risk-scores, and compliance-screens every incoming transaction from
`sample-transactions.json`, writing a single auditable outcome — `REJECTED`,
`CLEARED`, or `HELD_FOR_REVIEW` — for every transaction to `shared/results/`.

The pipeline's Mid-Level Objectives (`specification.md` section 2) drive the
design: transactions are checked for structural/currency/sign correctness before
anything else runs, every transaction that survives validation gets an additive
0-100 fraud risk score from timing, amount, cross-border, and channel signals,
and a final compliance pass screens against a watchlist and holds anything the
fraud stage flagged. Every stage appends a PII-free audit-trail entry
(`shared/results/audit_log.jsonl`) for every record it touches, and the run as a
whole produces a `shared/results/summary.json` with counts by outcome and reason
code. A static dashboard and a read-only MCP server both expose the same
`shared/results/` data for humans and for AI agents/tools.

## Pipeline stages

Each stage is a plain module under `pipeline/` with a single
`process_transaction(record: dict) -> dict` entry point; stages never import or
call each other directly — they only communicate through the
`shared/{input,processing,output,results}/` file protocol via the standard
message envelope (`message_id`, `timestamp`, `source_stage`, `target_stage`,
`message_type`, `data`).

- **Validation** (`pipeline/validator.py`) — Checks that all nine required
  fields are present (`MISSING_REQUIRED_FIELD` if not), parses `amount` with
  `decimal.Decimal(str(...))` (`INVALID_AMOUNT_FORMAT` on failure), enforces the
  sign convention per `transaction_type` (`transfer`/`wire_transfer` must be
  strictly positive -> `NON_POSITIVE_AMOUNT`; `refund` must be strictly negative
  -> `REFUND_MUST_BE_NEGATIVE`), and validates `currency` against a fixed,
  offline 40-code ISO 4217 allow-list (`CURRENCY_NOT_ISO4217`). Rejected records
  are written straight to `shared/results/` as terminal `REJECTED` outcomes and
  never reach Fraud Detection; validated records are normalized (`amount` as a
  string, `currency` upper-cased) and forwarded.
- **Fraud Detection** (`pipeline/fraud_detector.py`) — Never rejects a record on
  its own; it only computes and annotates an additive `risk_score` (capped at
  100) from four signals on the *validated* record: amount tier on
  `abs(amount)` (+60 for `> 50,000`, +40 for `> 10,000`, +15 for `> 5,000`,
  mutually exclusive, highest tier wins), off-hours UTC timestamp (`< 6` or
  `>= 22`, +20), cross-border destination (`metadata.country` not in the home
  set `{"US"}`, +15 — an unknown/missing country fails safe as cross-border),
  and `transaction_type == "wire_transfer"` (+10). The score maps to
  `risk_level` (`LOW` / `MEDIUM` >= 30 / `HIGH` >= 60) and `fraud_status`
  (`passed` for `LOW`, `flagged` otherwise); the annotated record always moves
  on to Compliance Check.
- **Compliance Check** (`pipeline/compliance_checker.py`) — The terminal stage
  for every record that survived Validation. Screens `source_account` and
  `destination_account` against a static watchlist constant
  (`WATCHLIST_ACCOUNTS = {"ACC-9999"}`); a hit overrides everything else and
  produces `HELD_FOR_REVIEW` / `WATCHLIST_MATCH` (with the matched account
  masked as `ACC-***<last 2 digits>` in the human-facing review note). Absent a
  watchlist hit, any record the fraud stage flagged is held with
  `FRAUD_RISK_FLAGGED`; everything else is `CLEARED`. Always writes exactly one
  terminal record to `shared/results/<transaction_id>.json`.

Running the pipeline against the bundled `sample-transactions.json` (8 records)
produces: 3 `CLEARED`, 4 `HELD_FOR_REVIEW` (3 `FRAUD_RISK_FLAGGED`, 1
`WATCHLIST_MATCH`), and 1 `REJECTED` (`CURRENCY_NOT_ISO4217`) — see
`HOWTORUN.md` to reproduce this run.

## Architecture

```
                         python orchestrator.py
                                  |
                                  v
                  sample-transactions.json (8 raw records)
                                  |
                                  v
        +----------------------------------------------------+
        |         shared/input/  (per-record envelope)        |
        +----------------------------------------------------+
                                  |
                                  v   shared/processing/
                        +-------------------+
                        |  Validation stage |
                        | pipeline/validator|
                        +-------------------+
                          |               |
                REJECTED  |               | VALIDATED
           (terminal)     |               v  shared/output/ -> shared/processing/
                          |     +-----------------------+
                          |     |  Fraud Detection stage |
                          |     | pipeline/fraud_detector|
                          |     +-----------------------+
                          |               |
                          |               v  shared/output/ -> shared/processing/
                          |     +-----------------------+
                          |     | Compliance Check stage |
                          |     |pipeline/compliance_    |
                          |     |checker                 |
                          |     +-----------------------+
                          |               |
                          v               v
        +----------------------------------------------------+
        |     shared/results/<transaction_id>.json (terminal) |
        |     shared/results/summary.json (run summary)       |
        |     shared/results/audit_log.jsonl (per-stage log)  |
        +----------------------------------------------------+
                     |                              |
                     v                              v
        frontend/ (static dashboard,        mcp/server.py
        fetches shared/results/*.json       ("pipeline-status" MCP server,
        via python -m http.server)          read-only tools/resource over
                                             shared/results/)
```

Every arrow between stages is a real file move through
`shared/{input,processing,output,results}/` — no stage imports another stage's
module. The front-end and the MCP server are both independent, read-only
consumers of `shared/results/`; neither one runs or mutates the pipeline.

## Tech stack

| Layer | Choice |
|---|---|
| Language / runtime | Python 3.12 (pinned in `mise.toml`; developed inside a `.venv`) |
| Pipeline stages | Plain modules under `pipeline/` (`validator.py`, `fraud_detector.py`, `compliance_checker.py`, `common.py`), file-in/file-out only |
| Orchestration | `orchestrator.py` — drives the file-based protocol, isolates per-record failures, writes `shared/results/summary.json` |
| Front-end | Static HTML/CSS/JS dashboard under `frontend/` (`index.html`, `app.js`, `styles.css`), no build step, served with any static file server |
| Custom MCP server | FastMCP, `mcp/server.py` (server name `pipeline-status`) |
| Docs MCP | `context7` (`.mcp.json`, queried for `decimal`/FastMCP patterns — see `research-notes.md`) |
| Test runner | pytest + pytest-cov (`tests/`, 69 tests, 99% coverage on `pipeline/` + `mcp/`) |
| Coverage gate | `.claude/hooks/check-coverage.sh`, a `PreToolUse` hook on `git push` that blocks below 80% total coverage |

See `HOWTORUN.md` for exact commands to run the pipeline, the dashboard, the
tests, and the MCP servers.
