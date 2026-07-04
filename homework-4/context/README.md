# Bug case directories

Each bug the pipeline works on gets its own directory here: `context/bugs/<bug-id>/`.

`<bug-id>` is a short, numbered slug, e.g. `001-negative-balance`. The pipeline's four
agents read and write files in this directory as they run:

```
context/bugs/<bug-id>/
├── bug-context.md              # seeded by Task 5: what the bug is, how to reproduce it
├── research/
│   ├── codebase-research.md    # produced upstream (Bug Researcher), before the pipeline's agents run
│   └── verified-research.md    # written by research-verifier
├── implementation-plan.md      # produced upstream (Bug Planner), before bug-fixer runs
├── fix-summary.md              # written by bug-fixer
├── security-report.md          # written by security-verifier
└── test-report.md              # written by unit-test-generator
```

Only one bug case directory should exist under `context/bugs/` at a time when running
`./run-pipeline.sh` without an explicit bug id — the four agents look for a single
subdirectory here and stop with an ambiguity error if there are zero or several.

This directory is currently empty (no `.claude/agents` here — see the repo's `.claude/`
folder). Task 5 will add the first real bug case, seeded with intentional bugs and a
security issue in the sample app under `src/`.
