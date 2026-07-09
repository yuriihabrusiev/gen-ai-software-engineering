# Transaction Processing Pipeline — Specification

> Ingest this file, implement the Low-Level Tasks, and generate the code that
> satisfies the High- and Mid-Level Objectives.

## 1. High-Level Objective

Validate, risk-score, and compliance-screen every incoming transaction from
`sample-transactions.json` through a three-stage, file-based pipeline, writing a
single auditable outcome record (rejected, cleared, or held for review) for every
transaction to `shared/results/`.

## 2. Mid-Level Objectives

1. Every transaction passes through the Validation stage first; any transaction
   with a missing required field, a non-ISO-4217 currency code, or an amount that
   violates the sign convention for its `transaction_type` (positive for
   `transfer`/`wire_transfer`, strictly negative for `refund`) is rejected with a
   machine-readable reason code before it ever reaches Fraud Detection — e.g.
   `TXN006` (currency `XYZ`) is rejected with `CURRENCY_NOT_ISO4217`.
2. Every validated transaction receives a numeric fraud risk score (0-100) from
   the Fraud Detection stage, computed from amount tier, off-hours timing (UTC
   hour < 6 or >= 22), cross-border destination country, and wire-transfer
   channel; transactions scoring >= 30 are marked `flagged`. This must produce
   distinguishable outcomes on the sample data: `TXN002` (score 50) and `TXN004`
   (score 35) are flagged, while `TXN003` (score 15, $9,999.99 — one cent under
   the $10,000 tier) and `TXN008` (score 0) pass.
3. Every transaction that reaches the Compliance Check stage (i.e. everything
   that was not rejected by Validation) is screened against a static sanctioned
   /watchlisted account list; any transaction whose `source_account` or
   `destination_account` appears on the watchlist is held for manual review with
   reason code `WATCHLIST_MATCH` regardless of its fraud score — e.g. `TXN003`
   is held despite its low fraud score because its `destination_account`
   (`ACC-9999`) is watchlisted. Any transaction the Fraud Detection stage flagged
   (score >= 30) that is not already held for a watchlist match is held for
   review with reason code `FRAUD_RISK_FLAGGED`; everything else is `CLEARED`.
4. Every outcome (`REJECTED`, `CLEARED`, `HELD_FOR_REVIEW`) is written as a
   terminal JSON record to `shared/results/<transaction_id>.json`, and the
   orchestrator produces a run summary (`shared/results/summary.json`) with
   counts per outcome and a breakdown of reason codes.
5. Every pipeline stage appends one structured audit-trail entry per record it
   touches (ISO 8601 UTC timestamp, stage name, `transaction_id`, outcome) to
   `shared/results/audit_log.jsonl`, and none of `source_account`,
   `destination_account`, or `description` ever appear in that log, in the
   summary, or in any console output in plaintext.

## 3. Implementation Notes

- **Monetary type**: amounts arrive as strings (e.g. `"25000.00"`, `"-100.00"`)
  and must be parsed with `decimal.Decimal(str(...))` at the point of first
  contact and kept as `Decimal` through every comparison, threshold check, and
  sum. `float` must never appear on the money code path, including in the
  fraud-scoring math.
- **Currency validation**: validate `currency` against a fixed, offline ISO 4217
  alphabetic-code allow-list (a Python `set` constant in `pipeline/validator.py`,
  e.g. `{"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", ...}`). Do not call an
  external API at runtime — validation must be deterministic and network-free.
  An unrecognized code (`TXN006`, currency `XYZ`) is rejected with reason code
  `CURRENCY_NOT_ISO4217`. (Agent 2 may consult context7 for a vetted currency
  list/library such as `pycountry`, but the runtime check itself must stay
  local/offline.)
- **Sign convention (refunds)**: `transaction_type` drives the required sign of
  `amount`. `transfer` and `wire_transfer` require `amount > 0`
  (`NON_POSITIVE_AMOUNT` if violated). `refund` requires `amount < 0`
  (`REFUND_MUST_BE_NEGATIVE` if violated) — `TXN007` (`-100.00 GBP`, type
  `refund`) is valid and must NOT be rejected on sign alone. Downstream fraud
  scoring always uses the transaction's absolute value (`abs(amount)`) for its
  amount-tier calculation, so a refund's magnitude is still risk-scored.
- **Off-hours / cross-border definitions**: off-hours means the transaction
  `timestamp`'s UTC hour is `< 6` or `>= 22` (`TXN004`, 02:47 UTC, qualifies).
  Cross-border means `metadata.country` is not in the home-country set
  `{"US"}` (the bank's domicile) — `TXN004` (`DE`) and `TXN007` (`GB`) qualify.
- **Fraud risk scoring** (all points additive, capped at 100):
  - Amount tier (using `abs(amount)`): `> 50,000` -> +60; `> 10,000` -> +40;
    `> 5,000` -> +15; otherwise +0. (Tiers are mutually exclusive — apply the
    highest tier that matches.)
  - Off-hours timestamp: +20
  - Cross-border destination: +15
  - `transaction_type == "wire_transfer"`: +10
  - Risk level: `score < 30` -> `LOW`; `30 <= score < 60` -> `MEDIUM`;
    `score >= 60` -> `HIGH`. `fraud_status` is `passed` for `LOW`, `flagged`
    for `MEDIUM`/`HIGH`.
- **Watchlist**: `pipeline/compliance_checker.py` holds a static constant
  `WATCHLIST_ACCOUNTS = {"ACC-9999"}` (a fictitious sanctioned/high-risk account
  used for deterministic testing against the sample data). Both
  `source_account` and `destination_account` are checked.
- **Logging / audit trail**: every stage appends one JSON Lines entry to
  `shared/results/audit_log.jsonl` of the shape
  `{"timestamp": "<ISO8601 UTC>", "stage": "<stage_name>", "transaction_id": "<id>", "outcome": "<outcome_or_reason_code>"}`.
  No other fields are permitted in this log.
- **PII handling**: `source_account`, `destination_account`, and `description`
  are never written to any log, the audit trail, the summary report, or console
  output in plaintext. When an account must appear in a human-facing message
  (e.g. a compliance hold reason), mask it as `ACC-***<last 2 digits>` (e.g.
  `ACC-1001` -> `ACC-***01`). `description` is never surfaced outside the
  original input record and the final `shared/results/<transaction_id>.json`
  file (which is treated as an internal record, not a log).
- **File-based protocol**: stages communicate only via JSON files moved through
  `shared/input/ -> shared/processing/ -> shared/output/ -> shared/results/`,
  using the standard message envelope (`message_id`, `timestamp`,
  `source_stage`, `target_stage`, `message_type`, `data`) from `TASKS.md`. No
  stage imports or calls another stage's module directly.
- **Per-record isolation**: a malformed or unparsable record (e.g. an
  unparsable `amount` string) must never crash the orchestrator for the rest of
  the batch — catch, record a `REJECTED` outcome with reason code
  `INVALID_AMOUNT_FORMAT` or `MISSING_REQUIRED_FIELD`, and continue.

## 4. Context

### Beginning state
- `sample-transactions.json` — 8 raw transaction records (`TXN001`-`TXN008`) at
  the repo root, covering: a normal domestic transfer, two high-value wire
  transfers, a transaction just under the $10,000 fraud tier, an off-hours
  cross-border transfer, an invalid-currency transaction, a negative-amount
  refund, and a routine transfer.
- `shared/` directories do not yet exist (the orchestrator creates
  `shared/input/`, `shared/processing/`, `shared/output/`, `shared/results/` on
  startup).
- No pipeline code, front-end, or tests exist yet.

### Ending state
- `pipeline/validator.py`, `pipeline/fraud_detector.py`,
  `pipeline/compliance_checker.py`, and `orchestrator.py` implemented and
  runnable end-to-end via `python orchestrator.py`.
- Every one of the 8 records in `sample-transactions.json` has exactly one
  corresponding outcome file in `shared/results/<transaction_id>.json`, plus
  `shared/results/summary.json` (counts by outcome/reason code) and
  `shared/results/audit_log.jsonl` (one line per stage per record).
- A simple front-end (`frontend/index.html` + `frontend/app.js`, no build step)
  that displays the current contents of `shared/results/` — pass/fail/held
  counts and per-transaction status.
- `research-notes.md` documenting at least 2 context7 queries made while
  building the pipeline (Agent 2's responsibility, not this spec's).
- Test suite in `tests/` with coverage >= 90% (the coverage gate hook in
  `.claude/settings.json` blocks `git push` below 80%).
- All inter-stage communication happened exclusively through the
  `shared/{input,processing,output,results}/` file-based protocol using the
  standard message envelope — no stage called another stage's code directly.

## 5. Low-Level Tasks

### Task: Validation Stage

```
Task: Validation Stage
Prompt: "Implement pipeline/validator.py with process_transaction(record: dict) -> dict.
Read a transaction record's `data` payload (transaction_id, timestamp,
source_account, destination_account, amount, currency, transaction_type,
description, metadata). Confirm all required fields are present
(MISSING_REQUIRED_FIELD if not). Parse `amount` as decimal.Decimal
(INVALID_AMOUNT_FORMAT if unparsable). Enforce the sign convention: amount > 0
for transaction_type in {transfer, wire_transfer} (NON_POSITIVE_AMOUNT if
violated), amount < 0 for transaction_type == refund (REFUND_MUST_BE_NEGATIVE
if violated). Validate `currency` against a fixed ISO 4217 allow-list constant
(CURRENCY_NOT_ISO4217 if unknown). On any failure, set status=REJECTED with the
matching reason_code, write the record straight to
shared/results/<transaction_id>.json, append an audit_log.jsonl entry with
outcome 'REJECTED:<reason_code>', and do not forward it further. On success, set
status=VALIDATED and write the message envelope to shared/output/ for the fraud
detector, and append an audit_log.jsonl entry with outcome 'VALIDATED'. Never
log source_account, destination_account, or description."
File to CREATE: pipeline/validator.py
Function to CREATE: process_transaction(record: dict) -> dict
Details: Reads `data.amount`, `data.currency`, `data.transaction_type`, and
presence of all required fields. Writes REJECTED terminal records directly to
shared/results/; writes VALIDATED records to shared/output/ for the next
stage. A rejection is any of MISSING_REQUIRED_FIELD, INVALID_AMOUNT_FORMAT,
NON_POSITIVE_AMOUNT, REFUND_MUST_BE_NEGATIVE, CURRENCY_NOT_ISO4217; anything
else is a pass-through with status=VALIDATED.
```

### Task: Fraud Detection Stage

```
Task: Fraud Detection Stage
Prompt: "Implement pipeline/fraud_detector.py with process_transaction(record: dict) -> dict.
Consume only records with status=VALIDATED from shared/processing/. Using
abs(decimal.Decimal(data['amount'])), compute an additive risk_score (int,
0-100 cap): +60 if amount > 50000, else +40 if amount > 10000, else +15 if
amount > 5000, else +0; +20 if the UTC hour of data['timestamp'] is < 6 or
>= 22; +15 if data['metadata']['country'] not in {'US'}; +10 if
data['transaction_type'] == 'wire_transfer'. Map risk_score to risk_level:
LOW (<30), MEDIUM (30-59), HIGH (>=60). Set fraud_status='passed' for LOW,
'flagged' for MEDIUM/HIGH. Attach risk_score, risk_level, fraud_status to the
record's data. Write the enriched envelope to shared/output/ for the
compliance checker (every validated record is forwarded — fraud detection
never terminates a record on its own). Append an audit_log.jsonl entry with
outcome 'flagged:<risk_level>' or 'passed:<risk_level>'. Never log
source_account, destination_account, or description."
File to CREATE: pipeline/fraud_detector.py
Function to CREATE: process_transaction(record: dict) -> dict
Details: Reads data.amount, data.timestamp, data.metadata.country,
data.transaction_type. Never rejects a record outright — it annotates
risk_score/risk_level/fraud_status and always forwards to shared/output/ for
Compliance Check, which makes the final hold/clear decision.
```

### Task: Compliance Check Stage

```
Task: Compliance Check Stage
Prompt: "Implement pipeline/compliance_checker.py with process_transaction(record: dict) -> dict.
Consume records annotated by the fraud detector from shared/processing/. Check
data['source_account'] and data['destination_account'] against the constant
WATCHLIST_ACCOUNTS = {'ACC-9999'}. If either matches, set
outcome='HELD_FOR_REVIEW', reason_code='WATCHLIST_MATCH'. Else if
data['fraud_status'] == 'flagged', set outcome='HELD_FOR_REVIEW',
reason_code='FRAUD_RISK_FLAGGED'. Otherwise set outcome='CLEARED' with no
reason_code. Write the final terminal record (including risk_score,
risk_level, fraud_status, outcome, reason_code) to
shared/results/<transaction_id>.json. Append an audit_log.jsonl entry with
outcome '<outcome>' (and ':<reason_code>' suffix when held). Mask
source_account/destination_account (ACC-***<last 2 digits>) in any
human-readable message; never write description anywhere in the log."
File to CREATE: pipeline/compliance_checker.py
Function to CREATE: process_transaction(record: dict) -> dict
Details: Reads data.source_account, data.destination_account,
data.fraud_status. This is the terminal stage for every record that survived
Validation — it always writes exactly one file to shared/results/ per
transaction_id, with outcome in {CLEARED, HELD_FOR_REVIEW}.
```

### Task: Orchestrator / Runner

```
Task: Orchestrator / Runner
Prompt: "Implement orchestrator.py with run_pipeline(input_path: str = 'sample-transactions.json') -> dict
and a main() CLI entry point. On startup, create shared/input/,
shared/processing/, shared/output/, shared/results/ if missing. Load every
record from sample-transactions.json, wrap each in the standard message
envelope (message_id=uuid4, timestamp=now UTC ISO8601, source_stage='orchestrator',
target_stage='validator', message_type='transaction', data=<record>), and write
one file per record to shared/input/. Move each record's file through
processing/ -> validator.process_transaction -> (if VALIDATED) output/ ->
processing/ -> fraud_detector.process_transaction -> output/ -> processing/ ->
compliance_checker.process_transaction -> results/. Isolate per-record
exceptions so one bad record cannot halt the batch (write it to results/ as
REJECTED with a generic INTERNAL_ERROR reason_code and log the exception,
without ever raising past run_pipeline for that record). After all records are
processed, write shared/results/summary.json with total count and counts by
outcome and by reason_code, and return that summary dict. Print a human
-readable summary to stdout with no PII."
File to CREATE: orchestrator.py
Function to CREATE: run_pipeline(input_path: str = "sample-transactions.json") -> dict
Details: Reads sample-transactions.json at input_path. Drives records through
validator -> fraud_detector -> compliance_checker using only the
shared/{input,processing,output,results}/ file protocol (no direct
cross-module calls to stage internals other than invoking each stage's public
process_transaction). Writes shared/results/summary.json as its final output
and returns the same summary dict for programmatic use (e.g. by the
front-end's dev server or tests).
```

### Task: Front-End Dashboard

```
Task: Front-End Dashboard
Prompt: "Build a static, no-build-step dashboard under frontend/ (index.html,
app.js, and an optional styles.css) that fetches and renders the contents of
shared/results/summary.json and the individual shared/results/<transaction_id>.json
files (served by a minimal local HTTP server, e.g. python -m http.server, or a
tiny Python server that also exposes shared/results/ as static files). Show:
total transaction count, counts per outcome (REJECTED / CLEARED /
HELD_FOR_REVIEW), a table listing each transaction_id with its outcome,
reason_code (if any), and risk_level, and a manual 'Refresh' control that
re-fetches the JSON files. Never render source_account, destination_account,
or description on the page."
File to CREATE: frontend/index.html, frontend/app.js
Function to CREATE: N/A (static dashboard) — frontend/app.js exposes a
renderDashboard() entry point invoked on page load and on 'Refresh' click.
Details: Reads shared/results/summary.json and shared/results/*.json (excluding
audit_log.jsonl) via fetch(). Purely a read-only viewer — it never writes to
shared/ and never triggers a pipeline run itself.
```
