---
description: Generate or refresh specification.md (and extend agents.md) for the transaction processing pipeline, following specification-TEMPLATE-hint.md.
argument-hint: [optional notes to steer the spec]
---

Produce or update `specification.md` for the transaction processing pipeline,
using the `spec-writer` subagent.

Steps:
1. Confirm `specification-TEMPLATE-hint.md`, `TASKS.md`, `agents.md`, and
   `sample-transactions.json` all exist at the repo root; stop and report if any
   are missing rather than inventing their content.
2. Delegate to the `spec-writer` subagent to write `specification.md` with all
   five required sections (High-Level Objective; Mid-Level Objectives;
   Implementation Notes; Context; Low-Level Tasks — one per pipeline stage,
   minimum 3 stages) exactly matching the structure in
   `specification-TEMPLATE-hint.md`.
3. Have `spec-writer` extend `agents.md`'s Domain Rules, Edge Case Handling, and
   Testing & Verification sections so they stay consistent with the concrete
   decisions made in `specification.md`.
4. If $ARGUMENTS is non-empty, treat it as additional constraints or preferences
   to fold into the spec (e.g. a specific fraud threshold, a preferred third
   stage) — do not silently ignore it.
5. Report back: the chosen three pipeline stages, the fraud threshold used, and
   a one-line summary of what changed in `agents.md`.
