#!/usr/bin/env bash
# Single-command entry point for the 4-agent bug-fix pipeline.
#
# Usage:
#   ./run-pipeline.sh [bug-id]
#
# If bug-id is omitted, the script looks for a single directory under
# context/bugs/ and uses that. It fails loudly if there are zero or more
# than one candidate, rather than guessing.
#
# Requires the `claude` CLI on PATH. Relies on .claude/agents/*.agent.md and
# .claude/skills/*/SKILL.md being loaded automatically by Claude Code, and on
# .claude/settings.json for non-interactive tool permissions.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v claude >/dev/null 2>&1; then
  echo "error: the 'claude' CLI is not on PATH. Install Claude Code first: https://code.claude.com" >&2
  exit 1
fi

BUG_ID="${1:-}"

if [[ -n "$BUG_ID" ]]; then
  BUG_DIR="context/bugs/${BUG_ID}"
  if [[ ! -d "$BUG_DIR" ]]; then
    echo "error: bug case directory '$BUG_DIR' does not exist." >&2
    exit 1
  fi
else
  CANDIDATES=()
  while IFS= read -r dir; do
    CANDIDATES+=("$dir")
  done < <(find context/bugs -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

  if [[ ${#CANDIDATES[@]} -eq 0 ]]; then
    echo "error: no bug case directories found under context/bugs/." >&2
    echo "Seed one first (see context/README.md), e.g. context/bugs/001-example/bug-context.md" >&2
    exit 1
  elif [[ ${#CANDIDATES[@]} -gt 1 ]]; then
    echo "error: multiple bug case directories found under context/bugs/ — pass one explicitly:" >&2
    echo "  ./run-pipeline.sh <bug-id>" >&2
    echo "Candidates:" >&2
    for dir in "${CANDIDATES[@]}"; do
      echo "  - $(basename "$dir")" >&2
    done
    exit 1
  fi

  BUG_DIR="${CANDIDATES[0]}"
  BUG_ID="$(basename "$BUG_DIR")"
fi

echo "==> Running 4-agent bug-fix pipeline for context/bugs/${BUG_ID}"

PROMPT=$(cat <<PROMPT_EOF
You are the orchestrator of a bug-fix pipeline operating on the bug case
directory "context/bugs/${BUG_ID}/". Run these stages IN ORDER. This is a
non-interactive, single run — do not ask the user for confirmation between
stages, and do not stop to ask permission for routine reads/edits/test runs.

STAGE 0 — Research (skip this stage entirely if
context/bugs/${BUG_ID}/research/codebase-research.md already exists):
investigate the bug described in context/bugs/${BUG_ID}/bug-context.md
yourself, using Read/Grep/Glob against the repository, and write
context/bugs/${BUG_ID}/research/codebase-research.md documenting the root
cause with exact file:line references and verbatim quoted snippets. Be
rigorous — the next stage will fact-check every claim you make here.

STAGE 1 — Research verification: delegate to the research-verifier subagent
to verify context/bugs/${BUG_ID}/research/codebase-research.md and produce
context/bugs/${BUG_ID}/research/verified-research.md. If its verdict is
FAIL, STOP the entire pipeline here — report that the research must be
corrected before proceeding, and do not run any later stage.

STAGE 2 — Planning (skip this stage entirely if
context/bugs/${BUG_ID}/implementation-plan.md already exists; only run it if
Stage 1's verdict was PASS or CONDITIONAL PASS): using the verified research,
write context/bugs/${BUG_ID}/implementation-plan.md listing the exact files,
before/after code, and test command needed to fix the bug. If the bug case
bundles multiple independent issues, give each its own scoped verification
command (e.g. a specific test file/test id) instead of the full test suite,
and reserve the full suite for one final check after all issues are fixed —
otherwise Bug Fixer will see an unrelated, not-yet-fixed issue's test still
failing after an earlier fix and stop prematurely.

STAGE 3 — Fix: delegate to the bug-fixer subagent to apply
context/bugs/${BUG_ID}/implementation-plan.md and produce
context/bugs/${BUG_ID}/fix-summary.md.

STAGE 4 — Post-fix verification: delegate to BOTH the security-verifier
subagent and the unit-test-generator subagent. They are independent of each
other and may run in either order (or concurrently, your choice). Each reads
context/bugs/${BUG_ID}/fix-summary.md and the changed files, and produces
context/bugs/${BUG_ID}/security-report.md and
context/bugs/${BUG_ID}/test-report.md respectively. Run this stage even if
Stage 3's fix was only partially applied, so the reports reflect the actual
state of the code — just flag the partial status clearly.

When done (or when stopped early), print a short final summary: which
stages ran, which were skipped and why, the research quality verdict, the
fix status, the security overall recommendation, and the test results.
PROMPT_EOF
)

TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT

if command -v jq >/dev/null 2>&1; then
  claude -p "$PROMPT" --permission-mode dontAsk --output-format json | tee "$TMP_JSON" | jq -r '.result // empty'
  IS_ERROR="$(jq -r '.is_error // false' "$TMP_JSON" 2>/dev/null || echo false)"
  if [[ "$IS_ERROR" == "true" ]]; then
    echo "==> Pipeline reported an error." >&2
    exit 1
  fi
else
  claude -p "$PROMPT" --permission-mode dontAsk
fi

echo "==> Pipeline finished. See context/bugs/${BUG_ID}/ for verified-research.md, fix-summary.md, security-report.md, and test-report.md."
