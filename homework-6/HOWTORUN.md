# How to Run — Transaction Processing Pipeline

All commands below assume your shell's working directory is the repo root:
`homework-6/`. They were verified against the actual repo state (Python 3.14.3
via `uv`, pytest 9.1.1, 69 tests, 99% coverage) as of this writing.

## 1. Environment setup

`mise` is the main environment manager for this project — it pins the Python
version and the `uv` version in `mise.toml`; `uv` (via `pyproject.toml` +
`uv.lock`) manages the virtualenv and dependencies. There is no `pip` /
`requirements.txt` / manual `venv` step.

1. Install [`mise`](https://mise.jdx.dev/getting-started.html) if you don't
   already have it, then install this project's pinned tools (Python 3.14,
   latest `uv`):
   ```bash
   mise install
   ```
2. Install project dependencies:
   ```bash
   mise run setup
   ```
   Equivalent direct `uv` command: `uv sync`. This creates `.venv/` and
   installs runtime deps (`fastmcp`, `starlette`, `uvicorn`) plus the dev
   group (`pytest`, `pytest-cov`, `ruff`, `ty`) from `uv.lock`.

## 2. Run the pipeline

1. From the repo root, run:
   ```bash
   mise run pipeline
   ```
   Equivalent direct command: `uv run python orchestrator.py`. (Optionally
   pass a different input file: `uv run python orchestrator.py path/to/other.json` —
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
   mise run dashboard
   ```
   Equivalent direct command: `uv run python -m http.server 8000`.
3. Open **http://localhost:8000/frontend/** in a browser.
4. The page shows total transaction count, per-outcome counts, a reason-code
   breakdown, and a per-transaction table (ID, outcome, reason code, risk
   level). Click "Refresh" to re-fetch after re-running the pipeline. The
   dashboard never renders `source_account`, `destination_account`, or
   `description`.

## 4. Run the test suite and coverage report

1. Run:
   ```bash
   mise run test
   ```
   Equivalent direct command:
   ```bash
   uv run pytest --cov=pipeline --cov=mcp --cov-report=term-missing
   ```
   (`pyproject.toml`'s `[tool.pytest.ini_options]` sets `pythonpath = ["."]`
   and `testpaths = ["tests"]`, so this works regardless of caller cwd.)
2. Expected result: 69 tests passed, 99% total coverage across
   `pipeline/common.py`, `pipeline/validator.py`, `pipeline/fraud_detector.py`,
   `pipeline/compliance_checker.py` (each at 100%), and `mcp/server.py` (98%,
   the only uncovered line being the `mcp.run()` call under
   `if __name__ == "__main__":`, which isn't exercised by tests by design).
3. A `PreToolUse` git hook (`.claude/hooks/check-coverage.sh`, wired in
   `.claude/settings.json`) automatically re-runs this same coverage command
   (via `uv run pytest`) before any `git push` and blocks the push (exit code
   2) if total coverage falls below 80%, or if `tests/` doesn't exist at all.
   No manual action is needed to trigger it.

## 4b. Lint and type checks

```bash
mise run lint        # uv run ruff check .
mise run lint:fix     # uv run ruff check --fix .
mise run typecheck    # uv run ty check
mise run check        # lint + typecheck + test
```

Expected result: `ruff check .` and `ty check` are both clean (`All checks
passed!`).

## 5. Start the MCP servers for a manual demo

Both servers are declared in `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "context7": { "command": "npx", "args": ["-y", "@upstash/context7-mcp@latest"] },
    "pipeline-status": { "command": "uv", "args": ["run", "python", "mcp/server.py"] }
  }
}
```

`pipeline-status` is invoked via `uv run` (not a bare `python`) so it always
resolves the project's `uv`-managed environment regardless of the calling
process's shell state.

1. **Automatic (recommended for a Claude Code demo):** open this repo in
   Claude Code (or any MCP-aware client that reads `.mcp.json`); it will start
   both `context7` and `pipeline-status` automatically. Run the pipeline first
   (step 2) so `pipeline-status` has real data to serve.
2. **Manual/standalone run of the custom server** (for testing outside an MCP
   client, e.g. with the `fastmcp` CLI or a manual STDIO client):
   ```bash
   uv run python mcp/server.py
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

## 6. Hosted demo deployment (Render)

The live demo at https://transaction-pipeline-demo.onrender.com/frontend/ runs
`webapp.py` (not part of the graded Task 2 deliverable — see that file's
docstring) as a Render free-tier web service.

**How it's configured:**
- Service: `transaction-pipeline-demo` (`srv-d95e74jtqb8s73eo1nbg`), free plan,
  region `oregon`.
- Repo: `https://github.com/yuriihabrusiev/gen-ai-software-engineering`,
  branch `homework-6-submission`, root directory `homework-6` (this is a
  monorepo — Render builds only the `homework-6/` subtree).
- Build command: `pip install uv && uv sync --frozen` (Render's Python
  runtime ships `pip` but not `uv`, so the build bootstraps `uv` via `pip`
  first, then uses it exclusively). Start command: `uv run python webapp.py`.
  Health check path: `/healthz`.
- Auto-deploy is on: every push to `homework-6-submission` triggers a new
  Render deploy automatically.

**Redeploying manually** (e.g. to force a rebuild without a new commit):
```bash
render deploys create srv-d95e74jtqb8s73eo1nbg
```

**Agent-friendly management:** Render's official MCP server is registered at
user scope (`claude mcp get render`, not in this repo's `.mcp.json` — that
file is reserved for the two servers Task 4 requires). Once a Claude Code
session picks it up (new sessions do automatically; a session already running
when the server was added needs a restart to see its tools), you can ask
Claude to inspect logs, check deploy status, or trigger a redeploy by name
instead of shelling out to `render` commands.

**Note on the free tier:** the service spins down after 15 minutes of no
traffic and takes ~30-60s to wake up on the next request — expected for a
demo, not a bug.
