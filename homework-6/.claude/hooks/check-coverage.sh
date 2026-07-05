#!/usr/bin/env bash
# PreToolUse hook: blocks `git push` if unit test coverage is below the required
# threshold. Wired up in .claude/settings.json under PreToolUse -> matcher "Bash".
# Reads the triggering command from stdin itself (rather than relying solely on
# the settings.json "if" filter) and no-ops on anything that isn't `git push`,
# since that filter is not reliably honored by every Claude Code build. Exit 2
# blocks the tool call (stderr is shown to Claude); exit 0 allows it.
set -uo pipefail

HOOK_INPUT="$(cat)"
COMMAND="$(printf '%s' "$HOOK_INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"

if [[ ! "$COMMAND" =~ ^[[:space:]]*git[[:space:]]+push([[:space:]]|$) ]]; then
  exit 0
fi

THRESHOLD=80
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" || exit 2

if [ ! -d tests ]; then
  echo "Coverage gate: no tests/ directory found. Write the test suite (Task 5) before pushing." >&2
  exit 2
fi

if [ -x "$PROJECT_DIR/.venv/bin/pytest" ]; then
  PYTEST="$PROJECT_DIR/.venv/bin/pytest"
elif command -v pytest >/dev/null 2>&1; then
  PYTEST="pytest"
else
  echo "Coverage gate: pytest not found (checked .venv/bin/pytest and PATH). Install dependencies (pip install -r requirements.txt) before pushing." >&2
  exit 2
fi

REPORT=$("$PYTEST" --cov=pipeline --cov=mcp --cov-report=term-missing -q 2>&1)
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
  echo "Coverage gate: test suite failed. Push blocked until tests pass." >&2
  echo "$REPORT" >&2
  exit 2
fi

TOTAL=$(echo "$REPORT" | grep -E '^TOTAL' | awk '{print $NF}' | tr -d '%')

if [ -z "$TOTAL" ]; then
  echo "Coverage gate: could not parse a coverage percentage from pytest-cov output." >&2
  echo "$REPORT" >&2
  exit 2
fi

if [ "$TOTAL" -lt "$THRESHOLD" ]; then
  echo "Coverage gate: FAILED. Total coverage is ${TOTAL}%, below the required ${THRESHOLD}%. Push blocked." >&2
  exit 2
fi

echo "Coverage gate: passed (${TOTAL}% >= ${THRESHOLD}%)." >&2
exit 0
