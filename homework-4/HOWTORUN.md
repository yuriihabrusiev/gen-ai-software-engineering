# How to Run

## Prerequisites

- [Claude Code](https://code.claude.com) CLI installed and authenticated (`claude` on
  your `PATH`).
- `jq` (optional) — if present, `run-pipeline.sh` uses it to detect success/failure from
  the run's JSON output; without it, the script still runs, just with plainer output.

No other setup is required: Claude Code automatically loads everything under `.claude/`
(agents, skills, and permissions) whenever a session is opened in this repository.

## Run the full pipeline (one command)

```bash
./run-pipeline.sh [bug-id]
```

- If you omit `bug-id`, the script looks for a single directory under `context/bugs/`
  and uses it. It fails with a clear message if there are zero or more than one.
- The script drives one non-interactive `claude -p` session that, in order:
  1. Writes `context/bugs/<bug-id>/research/codebase-research.md` if it doesn't already
     exist (investigates `bug-context.md` itself).
  2. Delegates to the **research-verifier** subagent → `research/verified-research.md`.
     Stops here if the verdict is **FAIL**.
  3. Writes `context/bugs/<bug-id>/implementation-plan.md` if it doesn't already exist.
  4. Delegates to the **bug-fixer** subagent → applies the plan, runs tests,
     `fix-summary.md`.
  5. Delegates to the **security-verifier** and **unit-test-generator** subagents (they
     run independently of each other) → `security-report.md` and `test-report.md`.
- Permissions for this non-interactive run come from `.claude/settings.json`
  (`permissions.allow` / `permissions.deny`) combined with `--permission-mode dontAsk`,
  so it never blocks on an interactive approval prompt.

**Note**: this requires a bug case to exist under `context/bugs/<bug-id>/` with at least
a `bug-context.md` describing the bug. That seeding is Task 5's job (the sample
application), which hasn't been added to this repo yet — see the root `README.md`.

## Run a single agent manually (for debugging one stage)

Start an interactive Claude Code session in this repo (`claude`) and ask directly, e.g.:

```
Use the research-verifier subagent to verify context/bugs/001-example/research/codebase-research.md
```

```
Use the bug-fixer subagent to apply context/bugs/001-example/implementation-plan.md
```

```
Use the security-verifier subagent on context/bugs/001-example/fix-summary.md
```

```
Use the unit-test-generator subagent on context/bugs/001-example/fix-summary.md
```

Each subagent will look under `context/bugs/` for the target directory itself if you
don't name one explicitly, but naming it avoids ambiguity when multiple bug cases exist.

## Where outputs land

All pipeline output files are written inside the bug's own case directory:

```
context/bugs/<bug-id>/
├── bug-context.md
├── research/
│   ├── codebase-research.md
│   └── verified-research.md
├── implementation-plan.md
├── fix-summary.md
├── security-report.md
└── test-report.md
```

## Adjusting permissions

`.claude/settings.json` currently allows `Read`, `Grep`, `Glob`, `Edit`, `Write`, and any
`Bash` command, while explicitly denying reads of `.env`/secrets files and destructive
commands (`rm -rf`, force-push, `git reset --hard`, `curl`, `sudo`). Tighten the `allow`
list (e.g. to specific test commands for your Task 5 stack) if you want a narrower
non-interactive permission surface.
