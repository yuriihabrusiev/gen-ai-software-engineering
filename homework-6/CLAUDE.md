# CLAUDE.md — Transaction Processing Pipeline (Homework 6 Capstone)

Author: **Yurii Habrusiev**. This file guides Claude Code while building this
capstone. `TASKS.md` is the assignment brief; once written, `specification.md` is
the authoritative technical spec — this file holds cross-cutting conventions that
must not be violated regardless of which agent/skill is active.

## Session status (update as work progresses)

As of this writing, **only scaffolding exists**: `TASKS.md`, `sample-transactions.json`,
`specification-TEMPLATE-hint.md`, the starter `agents.md`, and the four subagents /
three skills / coverage-gate hook under `.claude/`. Nothing below has been built yet:
`specification.md`, `orchestrator.py`, `pipeline/`, `frontend/`, `mcp/server.py`,
`.mcp.json`, `tests/`, `research-notes.md`, `README.md`, `HOWTORUN.md`,
`docs/presentation.pdf`, `docs/screenshots/`.

Build order for the next session:
1. `/write-spec` -> `specification.md` + extended `agents.md` (Task 1).
2. `pipeline-builder` subagent -> `orchestrator.py`, `pipeline/*.py`, `frontend/`,
   `.mcp.json` + `mcp/server.py`, `research-notes.md` with >= 2 context7 queries
   (Task 2 & 4).
3. `test-writer` subagent -> `tests/` at >= 90% coverage (Task 3 & 5).
4. `docs-writer` subagent -> `README.md`, `HOWTORUN.md`, presentation outline
   (Task 5).
5. Screenshots + `docs/presentation.pdf` export + PR description (manual, by the
   student).

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
