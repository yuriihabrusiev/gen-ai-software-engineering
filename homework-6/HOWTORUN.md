# How to Run — Transaction Processing Pipeline

All commands below assume your shell's working directory is the repo root:
`homework-6/`. They were verified against the actual repo state (Python 3.12.12
in the project's `.venv`, pytest 9.1.1, 69 tests, 99% coverage) as of this
writing.

## 1. Environment setup

1. Confirm Python 3.12+ is available (the project pins `python = "3.12"` in
   `mise.toml`; if you use `mise`, run `mise install` first).
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   This installs `fastmcp`, `pytest`, and `pytest-cov`.

## 2. Run the pipeline

1. From the repo root, run:
   ```bash
   python orchestrator.py
   ```
   (Optionally pass a different input file: `python orchestrator.py path/to/other.json` —
   it defaults to `sample-transactions.json`.)
2. This creates `shared/{input,processing,output,results}/` if they don't exist,
   drives all 8 records in `sample-transactions.json` through Validation ->
   Fraud Detection -> Compliance Check, and prints a PII-free summary, e.g.:
   ```
   Transaction Processing Pipeline - run summary
     Total transactions: 8
     Outcomes:
       CLEARED: 3
       HELD_FOR_REVIEW: 4
       REJECTED: 1
     Reason codes:
       CURRENCY_NOT_ISO4217: 1
       FRAUD_RISK_FLAGGED: 3
       WATCHLIST_MATCH: 1
     Results written to: shared/results
   ```
3. Inspect the output directly:
   - `shared/results/<transaction_id>.json` — one terminal record per transaction.
   - `shared/results/summary.json` — the run summary shown above, as JSON.
   - `shared/results/audit_log.jsonl` — one audit-trail line per stage per record
     (no `source_account`/`destination_account`/`description`).

## 3. Run the front-end dashboard

The dashboard (`frontend/index.html` + `frontend/app.js`) is a static,
no-build-step page that fetches `shared/results/summary.json` and each
`shared/results/<transaction_id>.json` via relative `fetch()` calls — it must be
served from the **repo root** (not from inside `frontend/`) so those paths
resolve.

1. Make sure you've run the pipeline at least once (step 2 above), so
   `shared/results/` has data to show.
2. From the repo root, start a static file server:
   ```bash
   python -m http.server 8000
   ```
3. Open **http://localhost:8000/frontend/** in a browser.
4. The page shows total transaction count, per-outcome counts, a reason-code
   breakdown, and a per-transaction table (ID, outcome, reason code, risk
   level). Click "Refresh" to re-fetch after re-running the pipeline. The
   dashboard never renders `source_account`, `destination_account`, or
   `description`.

## 4. Run the test suite and coverage report

1. With the virtual environment active, run:
   ```bash
   python -m pytest --cov=pipeline --cov=mcp --cov-report=term-missing
   ```
   (Plain `pytest` also works — `pytest.ini` sets `pythonpath = .` and
   `testpaths = tests`.)
2. Expected result: 69 tests passed, 99% total coverage across
   `pipeline/common.py`, `pipeline/validator.py`, `pipeline/fraud_detector.py`,
   `pipeline/compliance_checker.py` (each at 100%), and `mcp/server.py` (98%,
   the only uncovered line being the `mcp.run()` call under
   `if __name__ == "__main__":`, which isn't exercised by tests by design).
3. A `PreToolUse` git hook (`.claude/hooks/check-coverage.sh`, wired in
   `.claude/settings.json`) automatically re-runs this same coverage command
   before any `git push` and blocks the push (exit code 2) if total coverage
   falls below 80%, or if `tests/` doesn't exist at all. No manual action is
   needed to trigger it — it fires on the `Bash(git push *)` pattern.

## 5. Start the MCP servers for a manual demo

Both servers are declared in `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "context7": { "command": "npx", "args": ["-y", "@upstash/context7-mcp@latest"] },
    "pipeline-status": { "command": "python", "args": ["mcp/server.py"] }
  }
}
```

1. **Automatic (recommended for a Claude Code demo):** open this repo in
   Claude Code (or any MCP-aware client that reads `.mcp.json`); it will start
   both `context7` and `pipeline-status` automatically. Run the pipeline first
   (step 2) so `pipeline-status` has real data to serve.
2. **Manual/standalone run of the custom server** (for testing outside an MCP
   client, e.g. with the `fastmcp` CLI or a manual STDIO client):
   ```bash
   python mcp/server.py
   ```
   This starts the `pipeline-status` FastMCP server over STDIO. It only reads
   `shared/results/` — it never writes to or mutates pipeline state.
3. Once connected, exercise the read-only surface:
   - Tool `get_transaction_status(transaction_id)` — e.g. `"TXN003"` — returns
     that transaction's status/outcome/reason_code/risk fields (PII stripped),
     or `{"found": false, ...}` if it hasn't reached a terminal stage yet.
   - Tool `list_pipeline_results()` — returns every processed transaction
     (PII stripped) plus the latest `summary.json`.
   - Resource `pipeline://summary` — returns the latest
     `shared/results/summary.json` as formatted JSON text.
4. `context7` is a documentation-lookup server (used during development to
   research `decimal` and FastMCP usage patterns — see `research-notes.md`);
   it isn't tied to this pipeline's runtime data and can be queried
   independently (e.g. "look up FastMCP resource decorators").
