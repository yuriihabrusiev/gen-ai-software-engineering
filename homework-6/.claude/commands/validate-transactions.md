---
description: Validate all transactions in sample-transactions.json without running the full pipeline.
---

Validate all transactions in `sample-transactions.json` without processing them
through the rest of the pipeline.

Steps:
1. Run the validator stage in dry-run mode: `python pipeline/validator.py --dry-run`
   (dry-run must check every record and report outcomes without writing anything
   to `shared/`).
2. If the validator doesn't yet support `--dry-run`, report that instead of
   working around it — the flag is part of the Task 1 specification and should be
   implemented, not bypassed.
3. Report: total transaction count, valid count, invalid count, and the specific
   rejection reason for each invalid transaction (e.g. unknown currency code,
   missing required field, non-positive amount).
4. Show the results as a table: `transaction_id | status | reason` (reason blank
   for valid records).
