---
description: Run the transaction processing pipeline end-to-end and summarize the results.
---

Run the transaction processing pipeline end-to-end.

Steps:
1. Check that `sample-transactions.json` exists at the repo root; stop and report
   if it doesn't.
2. Clear the `shared/input/`, `shared/processing/`, `shared/output/`, and
   `shared/results/` directories (create them if they don't exist yet) so this
   run starts from a clean state.
3. Run the pipeline: `python orchestrator.py`.
4. Read every result file in `shared/results/` and show a summary: total
   transactions processed, count passed vs. rejected/flagged per stage, and the
   overall pass/fail counts.
5. Report any transactions that were rejected or flagged, with their
   `transaction_id` and the specific reason field from their result file.
6. If the run fails (non-zero exit, missing result files, or a record with no
   corresponding file in `shared/results/`), report that explicitly instead of
   only showing the transactions that did succeed.
