# Specification Template — Transaction Processing Pipeline

> This is the template `specification.md` must follow (Task 1 of `TASKS.md`). It is a
> banking/fintech variant of the general spec template used in prior homeworks, shaped
> around a multi-stage, file-based transaction pipeline. Fill in every bracketed
> placeholder; do not leave a section empty. The `/write-spec` skill and the
> `spec-writer` subagent (see `.claude/agents/spec-writer.md`) both target this exact
> structure.

```markdown
# Transaction Processing Pipeline — Specification

> Ingest this file, implement the Low-Level Tasks, and generate the code that
> satisfies the High- and Mid-Level Objectives.

## 1. High-Level Objective

[One sentence: what the pipeline does end-to-end, e.g. "Validate, risk-score, and
settle incoming transactions, writing an auditable outcome for every record."]

## 2. Mid-Level Objectives

[4-5 concrete, testable requirements. Each must be checkable against a real run of
the pipeline over `sample-transactions.json`. Example shape:]
- Transactions above $10,000 are flagged for fraud review with a numeric risk score
- Transactions with an invalid ISO 4217 currency or a non-positive amount are rejected
  before reaching fraud detection
- Rejected transactions are written to `shared/results/` with a machine-readable
  reason code
- All pipeline stages log operations with ISO 8601 timestamps and no PII in plaintext
- [One more objective tied to whichever third stage is chosen — compliance,
  settlement, or reporting]

## 3. Implementation Notes

- Monetary values: `decimal.Decimal` everywhere amounts are parsed, compared, or
  summed — never `float`. Amounts arrive as strings in the input JSON.
- Currency codes: validate against ISO 4217 (USD, EUR, GBP, JPY, ...); reject
  unknown codes (see `TXN006` in `sample-transactions.json`, currency `XYZ`).
- Logging: every stage emits a structured audit-trail entry with timestamp
  (ISO 8601, UTC), stage name, `transaction_id`, and outcome.
- PII: `source_account` / `destination_account` and any name/description fields are
  sensitive — never log them in plaintext; mask or hash before logging.
- File-based protocol: stages communicate only via JSON files moved through
  `shared/input/ -> shared/processing/ -> shared/output/ -> shared/results/`, using
  the standard message envelope from `TASKS.md` (`message_id`, `timestamp`,
  `source_stage`, `target_stage`, `message_type`, `data`).
- [Add any project-specific rule discovered while reading `sample-transactions.json`,
  e.g. how negative amounts (`TXN007`, a refund) or off-hours cross-border transfers
  (`TXN004`) should be treated.]

## 4. Context

### Beginning state
- `sample-transactions.json` — raw transaction records at the repo root
- `shared/` directories do not yet exist (the orchestrator creates them)
- No pipeline code exists yet

### Ending state
- All pipeline stage modules implemented and runnable via the orchestrator
- Every record in `sample-transactions.json` has a corresponding outcome file in
  `shared/results/`
- A pipeline summary report (counts by outcome, rejection reasons)
- Test coverage >= 90% (gate blocks push below 80%, see `.claude/settings.json`)
- A simple front-end showing pipeline results/status

## 5. Low-Level Tasks

[One entry per pipeline stage, minimum 3 stages: Validation, Fraud Detection, and at
least one of Compliance Check / Settlement Processing / Reporting. Use this exact
format for each — it is what the code-generation agent executes literally:]

### Task: [Pipeline Stage Name]

```
Task: [Pipeline Stage Name]
Prompt: "[Exact prompt you will give the code-generation agent]"
File to CREATE: pipeline/[stage_module].py
Function to CREATE: [function_name](record: dict) -> dict
Details: [What the stage checks, transforms, or decides; which fields it reads
from `data`; what it writes to `shared/output/` or `shared/results/`; what
constitutes a rejection vs. a pass-through.]
```

[Repeat for each stage: Validation, Fraud Detection, and the chosen third stage.
Add one final task for the orchestrator/runner itself, and one for the front-end.]
```
