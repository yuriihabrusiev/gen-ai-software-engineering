# AGENTS.md — Transaction Processing Pipeline (Starter)

## Purpose

This file guides an AI coding agent implementing the pipeline described in
`specification.md`. `specification.md` now exists (produced by the
`spec-writer` subagent via the `/write-spec` skill) and this file has been
extended to match its concrete decisions (stage choice, fraud-scoring formula,
refund sign convention, currency rejection code). No pipeline code exists yet.
Where this file and `specification.md` disagree, `specification.md` is
authoritative — this file restates the parts an agent must never violate while
writing code.

## Assumed Tech Stack

| Layer | Assumption | Notes |
|---|---|---|
| Language / runtime | Python 3.12+ (pinned to 3.14 in `mise.toml`/`.python-version`) | Chosen for continuity with this course's stack and `decimal.Decimal` support; pinned version matches this repo's other homeworks. |
| Pipeline stages | Plain Python modules under `pipeline/` | No web framework required for the pipeline itself — stages are file-in/file-out. |
| Front-end | Static HTML/CSS/JS dashboard under `frontend/` | Served by a minimal Python HTTP server; polls `shared/results/` for status. No build step. |
| Custom MCP server | FastMCP (`mcp/server.py`) | Exposes `get_transaction_status`, `list_pipeline_results`, and the `pipeline://summary` resource. |
| Test runner | pytest + pytest-cov, run via `uv run pytest` | Coverage gate (see `.claude/settings.json`) blocks `git push` below 80%. |
| Lint / types | `ruff` (`uv run ruff check .`) and `ty` (`uv run ty check`) | Both must be clean before pushing; see `mise run check`. |
| Tooling | `mise` (env/tool-version manager) + `uv` (dependency/venv manager) | Dependencies live in `pyproject.toml` / `uv.lock` — no `pip`/`requirements.txt`. |

## Domain Rules (non-negotiable)

- Money is always parsed and compared as `decimal.Decimal`, never `float`. Amounts
  arrive as strings in `sample-transactions.json` and in every inter-stage message.
- Currency codes are validated against a fixed, offline ISO 4217 allow-list
  constant in `pipeline/validator.py`. An unknown code (e.g. `TXN006`'s `XYZ`) is a
  validation rejection with reason code `CURRENCY_NOT_ISO4217`, not a crash.
- Stages communicate only through the file-based protocol in `shared/{input,
  processing,output,results}/`, using the standard message envelope (`message_id`,
  `timestamp`, `source_stage`, `target_stage`, `message_type`, `data`). No stage
  calls another stage's code directly.
- Every stage writes a structured audit-trail log entry (ISO 8601 UTC timestamp,
  stage name, `transaction_id`, outcome) for every record it processes, pass or
  reject, appended to `shared/results/audit_log.jsonl` (JSON Lines, one entry per
  stage per record).
- `source_account`, `destination_account`, and any free-text `description` field are
  sensitive. Never write them to logs in plaintext. When an account must appear in
  a human-facing message, mask it as `ACC-***<last 2 digits>`.
- The three pipeline stages are, in order: **Validation** (`pipeline/validator.py`)
  -> **Fraud Detection** (`pipeline/fraud_detector.py`) -> **Compliance Check**
  (`pipeline/compliance_checker.py`). Compliance Check was chosen as the third
  stage because it is the natural terminal decision point for a risk-scored
  transaction (watchlist screening + hold/clear), not because it was the only
  option available — see `specification.md` section 1/5 for the rationale.
- **Fraud risk scoring formula** (`pipeline/fraud_detector.py`, additive, capped at
  100, computed on `abs(amount)`): amount `> 50,000` -> +60; else `> 10,000` ->
  +40; else `> 5,000` -> +15; else +0. Off-hours (`timestamp` UTC hour `< 6` or
  `>= 22`) -> +20. Cross-border (`metadata.country` not in the home-country set
  `{"US"}`) -> +15. `transaction_type == "wire_transfer"` -> +10. Risk level:
  `< 30` = `LOW` (`fraud_status="passed"`), `30-59` = `MEDIUM`, `>= 60` = `HIGH`
  (both `MEDIUM`/`HIGH` set `fraud_status="flagged"`). Fraud Detection never
  rejects a record itself — it always forwards to Compliance Check, which makes
  the final hold/clear call.
- **Compliance Check decision rule** (`pipeline/compliance_checker.py`): a static
  `WATCHLIST_ACCOUNTS = {"ACC-9999"}` constant is checked against both
  `source_account` and `destination_account` first (match -> `HELD_FOR_REVIEW` /
  `WATCHLIST_MATCH`, overriding fraud score); then any `fraud_status == "flagged"`
  record not already held -> `HELD_FOR_REVIEW` / `FRAUD_RISK_FLAGGED`; everything
  else -> `CLEARED`. This is the only stage that writes a terminal record to
  `shared/results/`.

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
  rejection path, and any boundary the stage introduces (e.g. the $10,000/$50,000
  fraud-scoring amount tiers, the 30/60 risk-score flag/HIGH boundaries, an unknown
  currency code, the refund sign-convention carve-out).
- Validator tests must cover all five reason codes: `MISSING_REQUIRED_FIELD`,
  `INVALID_AMOUNT_FORMAT`, `NON_POSITIVE_AMOUNT`, `REFUND_MUST_BE_NEGATIVE`,
  `CURRENCY_NOT_ISO4217`.
- Fraud detector tests must assert the exact scores from `sample-transactions.json`
  (e.g. `TXN002`=50/MEDIUM, `TXN003`=15/LOW despite being $0.01 under the $10,000
  tier, `TXN004`=35/MEDIUM, `TXN005`=70/HIGH) — treat these as regression fixtures,
  not just "flag vs. not flagged" assertions.
- Compliance checker tests must cover both hold reasons independently: a
  watchlist match (`WATCHLIST_MATCH`, e.g. `TXN003`'s destination `ACC-9999`)
  overriding a low fraud score, and a fraud-flagged record with no watchlist hit
  (`FRAUD_RISK_FLAGGED`).
- One integration test runs the full orchestrator over a small fixture set and
  asserts every input record has a corresponding file in `shared/results/`, and
  that `shared/results/summary.json` counts match the expected outcome
  distribution.
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
- **Refund sign convention (resolved, see `specification.md` section 3)**: a
  negative amount is not automatically invalid. `transaction_type` determines the
  required sign: `transfer`/`wire_transfer` require `amount > 0`
  (`NON_POSITIVE_AMOUNT` if violated); `refund` requires `amount < 0`
  (`REFUND_MUST_BE_NEGATIVE` if violated). `TXN007` (`-100.00 GBP`, `refund`) is
  valid and must pass Validation. Fraud scoring always uses `abs(amount)`, so a
  refund's magnitude is still risk-scored like any other transaction.
- **Invalid currency (resolved)**: an unrecognized ISO 4217 code is rejected at
  Validation with reason code `CURRENCY_NOT_ISO4217` (see `TXN006`, currency
  `XYZ`) and never reaches Fraud Detection or Compliance Check.
- **Watchlist overrides fraud score**: a `WATCHLIST_MATCH` hold at Compliance
  Check takes priority over — and is reported independently of — the fraud
  detector's `risk_level`. A transaction can be `LOW` risk and still end up
  `HELD_FOR_REVIEW` (e.g. `TXN003`).
- Never let one malformed record crash the orchestrator run for the rest of the
  batch — isolate per-record failures and record them as a `REJECTED` outcome
  (reason code `INTERNAL_ERROR` for unexpected exceptions, distinct from the
  five validation reason codes).

## Adding New Features

1. Add or update the relevant Mid-Level Objective in `specification.md` first.
2. Write the Low-Level Task (exact `Task:` / `Prompt:` / `File to CREATE:` /
   `Function to CREATE:` / `Details:` block) before writing code.
3. Confirm the new stage/feature uses the existing file-based message envelope and
   audit-logging path rather than a parallel implementation.
4. Add or update tests for the new behavior; re-run the coverage gate locally
   before pushing.
