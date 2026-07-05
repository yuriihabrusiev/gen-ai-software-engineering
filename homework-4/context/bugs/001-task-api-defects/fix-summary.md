# Fix Summary: 001-task-api-defects

Plan executed: `context/bugs/001-task-api-defects/implementation-plan.md`
(three independent, unrelated issues, applied and verified in order).

## Changes Made

### Issue 1 — Stats endpoint crashes when there are no tasks

- **File**: `src/task_tracker_api/store.py`
- **Location**: `stats()` function (was lines 65-74)
- **Before**:
  ```python
  def stats() -> dict:
      total = len(tasks)
      completed_count = sum(1 for task in tasks.values() if task.completed)
      # SEEDED BUG: no guard for total == 0, raises ZeroDivisionError.
      percent_complete = round(completed_count / total * 100, 1)
      return {
          "total": total,
          "completed": completed_count,
          "percent_complete": percent_complete,
      }
  ```
- **After**:
  ```python
  def stats() -> dict:
      total = len(tasks)
      completed_count = sum(1 for task in tasks.values() if task.completed)
      percent_complete = round(completed_count / total * 100, 1) if total else 0
      return {
          "total": total,
          "completed": completed_count,
          "percent_complete": percent_complete,
      }
  ```
- **Test result**: PASS
  ```
  uv run pytest tests/test_main.py::test_stats_with_no_tasks_returns_zero_percent -v
  tests/test_main.py::test_stats_with_no_tasks_returns_zero_percent PASSED [100%]
  1 passed, 1 warning in 0.01s
  ```

### Issue 2 — Priority sort returns the wrong order

- **File**: `src/task_tracker_api/store.py`
- **Location**: top-of-file import statement, plus `list_tasks()` function (was lines 22-33)
- **Before** (import line):
  ```python
  from task_tracker_api.models import Task, TaskCreate
  ```
- **Before** (function):
  ```python
  def list_tasks(completed: bool | None = None, sort: str | None = None) -> list[Task]:
      results = list(tasks.values())

      if completed is not None:
          results = [task for task in results if task.completed == completed]

      if sort == "priority":
          # SEEDED BUG: plain alphabetical sort on the enum value gives
          # high, low, medium — not the correct severity order.
          results = sorted(results, key=lambda t: t.priority.value)

      return results
  ```
- **After** (import line):
  ```python
  from task_tracker_api.models import Priority, Task, TaskCreate
  ```
- **After** (function):
  ```python
  _PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


  def list_tasks(completed: bool | None = None, sort: str | None = None) -> list[Task]:
      results = list(tasks.values())

      if completed is not None:
          results = [task for task in results if task.completed == completed]

      if sort == "priority":
          results = sorted(results, key=lambda t: _PRIORITY_ORDER[t.priority])

      return results
  ```
- **Test result**: PASS
  ```
  uv run pytest tests/test_main.py::test_tasks_sorted_by_priority_high_to_low -v
  tests/test_main.py::test_tasks_sorted_by_priority_high_to_low PASSED [100%]
  1 passed, 1 warning in 0.01s
  ```

### Issue 3 — Admin bulk-delete endpoint: unsafe credential handling

- **File**: `src/task_tracker_api/main.py`
- **Location**: top-of-file imports and `ADMIN_API_KEY` constant (was lines 1-21), and the `delete_all_tasks` handler (was lines 62-68)
- **Before** (imports/constant):
  ```python
  from fastapi import FastAPI, Header, HTTPException, Response

  from task_tracker_api.models import Task, TaskCreate
  from task_tracker_api.store import (
      clear_all,
      complete_task,
      create_task,
      delete_task,
      get_task,
      list_tasks,
      stats,
  )

  app = FastAPI(
      title="Task Tracker API",
      version="0.1.0",
      description="A small in-memory REST API for tracking tasks.",
  )

  # SEEDED SECURITY ISSUE: hardcoded admin key checked with plain equality.
  ADMIN_API_KEY = "supersecret-admin-key-123"
  ```
- **Before** (handler):
  ```python
  @app.delete("/admin/tasks", status_code=204)
  def delete_all_tasks(x_admin_key: str = Header(...)) -> Response:
      if x_admin_key == ADMIN_API_KEY:
          clear_all()
          return Response(status_code=204)
      else:
          raise HTTPException(status_code=403, detail="Forbidden")
  ```
- **After** (imports/constant):
  ```python
  import hmac
  import os

  from fastapi import FastAPI, Header, HTTPException, Response

  from task_tracker_api.models import Task, TaskCreate
  from task_tracker_api.store import (
      clear_all,
      complete_task,
      create_task,
      delete_task,
      get_task,
      list_tasks,
      stats,
  )

  app = FastAPI(
      title="Task Tracker API",
      version="0.1.0",
      description="A small in-memory REST API for tracking tasks.",
  )

  ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "dev-local-admin-key-000")
  ```
- **After** (handler):
  ```python
  @app.delete("/admin/tasks", status_code=204)
  def delete_all_tasks(x_admin_key: str = Header(...)) -> Response:
      if hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
          clear_all()
          return Response(status_code=204)
      else:
          raise HTTPException(status_code=403, detail="Forbidden")
  ```
- **Test result**: N/A by design. No automated test exists for this issue
  (per the plan and `bug-context.md` Notes). Verified by re-reading the
  applied diff in `src/task_tracker_api/main.py`: the hardcoded literal
  `"supersecret-admin-key-123"` is gone, `ADMIN_API_KEY` is now sourced from
  `os.environ.get("ADMIN_API_KEY", "dev-local-admin-key-000")` (default
  matches `mise.toml`'s local-dev value), and the comparison in
  `delete_all_tasks` now uses `hmac.compare_digest` instead of `==`.

## Overall Status

The plan was applied in full. All three independent issues were fixed exactly
as specified in `implementation-plan.md`:

1. `stats()` ZeroDivisionError guard — applied, scoped test passed.
2. `list_tasks()` priority sort order — applied (including the `Priority`
   import and the new `_PRIORITY_ORDER` mapping), scoped test passed.
3. `main.py` admin key hardening (env var sourcing + `hmac.compare_digest`) —
   applied, verified by diff re-read (no automated test exists for this issue
   by design).

The final full-suite check (`uv run pytest`) passed with 7 passed, 0 failed.

No before-code mismatches were encountered; the "before" snippets in the plan
matched the actual repository contents exactly for both `store.py` and
`main.py` prior to editing. No out-of-scope issues were noticed during this
session.

## Manual Verification

1. Run the scoped test for Issue 1:
   ```
   cd /Users/yuriihabrusiev/Developer/yuriihabrusiev/gen-ai-software-engineering/homework-4
   uv run pytest tests/test_main.py::test_stats_with_no_tasks_returns_zero_percent -v
   ```
   Expected: `1 passed`.

2. Run the scoped test for Issue 2:
   ```
   uv run pytest tests/test_main.py::test_tasks_sorted_by_priority_high_to_low -v
   ```
   Expected: `1 passed`.

3. Run the full test suite:
   ```
   uv run pytest
   ```
   Expected: `7 passed`.

4. Manually verify Issue 3 (admin key hardening) by starting the dev server
   and issuing curl requests:
   ```
   ADMIN_API_KEY=dev-local-admin-key-000 uv run fastapi dev src/task_tracker_api/main.py &
   curl -i -X DELETE http://127.0.0.1:8000/admin/tasks -H "X-Admin-Key: dev-local-admin-key-000"
   # Expected: HTTP/1.1 204 No Content

   curl -i -X DELETE http://127.0.0.1:8000/admin/tasks -H "X-Admin-Key: wrong-key"
   # Expected: HTTP/1.1 403 Forbidden with body {"detail":"Forbidden"}
   ```
   Stop the dev server afterward (e.g. `kill %1` or `fg` then Ctrl-C).

5. Confirm no hardcoded secret remains by inspecting the file directly:
   ```
   grep -n "ADMIN_API_KEY" src/task_tracker_api/main.py
   ```
   Expected output shows only
   `ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "dev-local-admin-key-000")`
   — no hardcoded literal such as `supersecret-admin-key-123`.

## References

Files touched:
- `src/task_tracker_api/store.py`
- `src/task_tracker_api/main.py`

Test commands run during this session:
- `uv run pytest tests/test_main.py::test_stats_with_no_tasks_returns_zero_percent -v` (passed)
- `uv run pytest tests/test_main.py::test_tasks_sorted_by_priority_high_to_low -v` (passed)
- `uv run pytest` (final full-suite check, 7 passed)
