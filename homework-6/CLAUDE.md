# CLAUDE.md — Transaction Processing Pipeline (Homework 6 Capstone)

Author: **Yurii Habrusiev**. This file guides Claude Code while building this
capstone. `TASKS.md` is the assignment brief; once written, `specification.md` is
the authoritative technical spec — this file holds cross-cutting conventions that
must not be violated regardless of which agent/skill is active.

## Session status (update as work progresses)

Tasks 1-5's automatable parts are all done: `specification.md` / extended
`agents.md` (Task 1); `orchestrator.py`, `pipeline/{common,validator,
fraud_detector,compliance_checker}.py`, `frontend/`, `mcp/server.py`,
`.mcp.json`, `research-notes.md` (Task 2/4); `tests/` — 69 tests, 99% coverage
on `pipeline/`+`mcp/`, coverage-gate hook verified passing (Task 3); `README.md`
(credits Yurii Habrusiev), `HOWTORUN.md`, `docs/presentation-outline.md` (Task
5 docs). All verified independently against real command output, not just
agent self-reports. `docs/presentation.pdf` exported (11-slide HTML deck ->
headless Chrome print-to-pdf) and linked in the PR. PR #14 opened against
`main`, no reviewer assigned yet per user's request.

Extra mile (beyond the assignment): `webapp.py` wraps the pipeline as a
persistent Starlette/uvicorn service (PII-scrubbed `/shared/results/...`,
`POST /api/run`) and is deployed live on Render's free tier at
https://transaction-pipeline-demo.onrender.com/frontend/ (service
`srv-d95e74jtqb8s73eo1nbg`, auto-deploys on push to this branch). Render's
official MCP server is registered at user scope (not in this repo's
`.mcp.json`) for agent-driven redeploys in future sessions. See
`HOWTORUN.md`'s "Hosted demo deployment" section.

Still outstanding, and cannot be done by an agent — manual/student steps only:
1. Capture the 6 required screenshots into `docs/screenshots/` (directory
   doesn't exist yet): `pipeline-run.png`, `frontend.png`, `test-coverage.png`,
   `skill-run-pipeline.png`, `hook-trigger.png`, `mcp-interaction.png`.
2. Embed/link the screenshots in the PR #14 description (see `TASKS.md`'s
   Submission section for the required content list), and assign a reviewer
   when ready.

## Tech stack (decided)

| Layer | Choice |
|---|---|
| Language / runtime | Python 3.12+ |
| Pipeline stages | Plain modules under `pipeline/`, file-in/file-out |
| Front-end | Static HTML/CSS/JS dashboard under `frontend/`, no build step |
| Custom MCP server | FastMCP, `mcp/server.py` |
| Docs MCP | context7 (`.mcp.json`, to be added alongside the pipeline in step 2) |
| Test runner | pytest + pytest-cov |

## Non-negotiable domain rules

- Money is always `decimal.Decimal`. Amounts arrive as strings — never cast to
  `float` at any point, including intermediate calculations.
- Currency codes are validated against ISO 4217.
- Stages never call each other's code directly. All inter-stage communication goes
  through the file-based protocol: `shared/input/ -> shared/processing/ ->
  shared/output/ -> shared/results/`, using the standard message envelope
  (`message_id`, `timestamp`, `source_stage`, `target_stage`, `message_type`,
  `data`) defined in `TASKS.md`.
- Every stage writes a structured audit-trail log entry (ISO 8601 UTC timestamp,
  stage name, `transaction_id`, outcome) for every record — pass or reject.
- `source_account`, `destination_account`, and any free-text description are
  sensitive: never write them to logs or console output in plaintext.
- See `agents.md` for the full, extendable rule set — it is authoritative for
  anything not repeated here.

## Repository layout (target)

```
homework-6/
├── TASKS.md                        # assignment brief
├── specification.md                # Task 1 output (spec-writer)
├── specification-TEMPLATE-hint.md  # template spec-writer follows
├── agents.md                       # extended by spec-writer
├── sample-transactions.json        # input fixture
├── orchestrator.py                 # Task 2 output (pipeline-builder)
├── pipeline/
│   ├── validator.py
│   ├── fraud_detector.py
│   └── <third_stage>.py
├── frontend/                       # Task 2 required front-end
├── mcp/server.py                   # Task 4 custom FastMCP server
├── .mcp.json                       # context7 + pipeline-status (repo root, not .claude/)
├── research-notes.md               # Task 4: >= 2 context7 queries logged
├── shared/{input,processing,output,results}/
├── tests/                          # Task 5 output (test-writer)
├── docs/{screenshots/,presentation.pdf}
├── README.md                       # Task 5 output (docs-writer) — must credit Yurii Habrusiev
└── HOWTORUN.md
```

## Claude Code harness already in place

- **Subagents** (`.claude/agents/`): `spec-writer` (Agent 1), `pipeline-builder`
  (Agent 2), `test-writer` (Agent 3), `docs-writer` (Agent 4) — one per capstone
  role in `TASKS.md`.
- **Skills** (`.claude/commands/`): `/write-spec`, `/run-pipeline`,
  `/validate-transactions`.
- **Coverage gate hook** (`.claude/settings.json` + `.claude/hooks/check-coverage.sh`):
  a `PreToolUse` hook on `Bash` matching `git push *` that runs
  `pytest --cov=pipeline --cov=mcp` and blocks the push (exit 2) if total coverage
  is below 80%, or if `tests/` doesn't exist yet at all.

## Working conventions

- Don't jump ahead of the build order above — e.g. don't write pipeline code before
  `specification.md` exists, and don't write tests before the stage they test is
  implemented.
- Each subagent stays in its lane (see its own file under `.claude/agents/`) —
  `pipeline-builder` doesn't edit `specification.md`, `test-writer` doesn't
  redesign pipeline logic to make a test pass, `docs-writer` doesn't touch code.
- Every technical claim in documentation must be verified against real command
  output, not assumed from the spec.
