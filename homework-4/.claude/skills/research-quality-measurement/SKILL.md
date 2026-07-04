---
description: Defines the research-quality rubric (levels, criteria, and pass/fail threshold) used to grade a verified-research.md report. Use whenever assessing how trustworthy a codebase research document is before acting on it (e.g. before a Bug Planner or Bug Fixer consumes it).
---

# Research Quality Measurement

A rubric for grading how trustworthy a codebase research document is, based on
how well its claims hold up against the actual source code. Use this skill
any time you need to assign a Research Quality level to a research document —
do not invent an ad hoc scale.

## The four levels

Levels are ordered from best to worst. Assign exactly one level to the
document as a whole.

### EXCELLENT
- Every file:line reference resolves to a real location in the codebase.
- Every quoted code snippet matches the source **verbatim** (whitespace and
  minor formatting differences are tolerated; semantic differences are not).
- Research covers the primary call site **and** related call sites / edge
  cases / callers that a fix would need to consider (not just the one
  obvious spot).
- No fabricated files, functions, symbols, or behavior of any kind.

### GOOD
- All file:line references resolve correctly and all snippets match source
  verbatim.
- Minor completeness gaps only: e.g. one secondary call site or edge case
  is missing, but nothing that would mislead a planner about the shape of
  the fix.
- No fabrication.

### FAIR
- One or more references or snippets contain **minor** inaccuracies (e.g. an
  off-by-a-few-lines citation, a snippet with small drift from current
  source, a stale line number after a recent refactor) that do not change
  the substance of the claim.
- No outright fabrication (no invented files/functions/behavior), but
  completeness is noticeably weak — an important call site or edge case is
  missing.
- Corrections needed, but the overall narrative is still directionally
  trustworthy.

### POOR
- One or more file:line references point to files/lines that do not exist,
  or one or more snippets do not match the real source in substance.
- Any evidence of fabrication: invented files, functions, APIs, or described
  behavior that isn't in the code.
- Claims asserted without any traceable file:line support.
- Research is missing large, obviously-relevant portions of the affected
  code path.

## Dimensions used to assign a level

1. **Reference accuracy** — do file:line citations resolve to real
   locations in the repository?
2. **Snippet fidelity** — do quoted code snippets match the actual source
   exactly (or near-exactly, allowing only trivial whitespace drift)?
3. **Completeness** — does the research cover the relevant call sites,
   callers, and edge cases, not just the single most obvious location?
4. **Absence of fabrication** — no invented files, functions, symbols, or
   described behavior that doesn't exist in the codebase.

## Decision procedure / checklist

Work through these steps in order; the first rule that applies determines
the level.

1. Open every file:line reference in the research document. If **any**
   reference does not resolve (file doesn't exist, or the cited lines don't
   contain what's claimed) → the document cannot be better than **POOR**.
2. Compare every quoted snippet against the real source at that location.
   If **any** snippet is substantively different from the source (not just
   whitespace) → **POOR**.
3. If any claim describes a file, function, API, or behavior that does not
   exist anywhere in the codebase (fabrication) → **POOR**, regardless of
   how accurate the rest of the document is.
4. If all references resolve and all snippets match, but there are minor
   citation drift issues (e.g., a line number a few lines off due to
   unrelated edits) → at most **FAIR**; downgrade further to **POOR** if
   more than one such issue exists or if it changes the meaning of the
   claim.
5. Among documents that pass steps 1–3 cleanly, judge completeness:
   - Covers primary site plus related call sites/edge cases → **EXCELLENT**.
   - Covers primary site well with only a small, non-critical gap →
     **GOOD**.
   - Covers primary site but misses an important secondary site or edge
     case → **FAIR**.
6. When in doubt between two adjacent levels, choose the lower (more
   conservative) one.

## Pass / fail threshold

- **EXCELLENT** and **GOOD** are **PASS** — safe to hand off to a Bug
  Planner or Bug Fixer as-is.
- **FAIR** is a **CONDITIONAL PASS** — usable, but the discrepancies and
  completeness gaps must be explicitly listed so downstream agents can
  compensate; prefer requesting a correction pass if time allows.
- **POOR** is a **FAIL** — do not hand off. The research must be redone (or
  the specific fabricated/incorrect claims must be stripped and the
  document re-verified) before any planning or fixing work proceeds.

## How to report the level

When writing a Research Quality Assessment, always state:
1. The assigned level (one of EXCELLENT / GOOD / FAIR / POOR).
2. Which dimension(s) drove the assignment (cite the specific rule from the
   decision procedure above).
3. The pass/fail/conditional-pass verdict per the threshold above.
