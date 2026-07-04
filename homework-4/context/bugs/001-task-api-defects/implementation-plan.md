# Implementation Plan: 001-task-api-defects

Based on `context/bugs/001-task-api-defects/research/verified-research.md`
(verdict: PASS, quality: EXCELLENT). Three independent, unrelated issues —
apply and verify each separately, then run the full suite once at the end.

## Issue 1 — Stats endpoint crashes when there are no tasks

**File**: `src/task_tracker_api/store.py`

**Before** (lines 65-74):

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

**After**:

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

Guard the division: when `total == 0`, `percent_complete` is `0` directly
instead of dividing by zero. The `SEEDED BUG` comment is removed since the bug
it documents is now fixed.

**Verification command**:

```
uv run pytest tests/test_main.py::test_stats_with_no_tasks_returns_zero_percent -v
```

## Issue 2 — Priority sort returns the wrong order

**File**: `src/task_tracker_api/store.py`

**Before** (lines 22-33):

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

**After**:

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

Sort by an explicit severity rank (high=0, medium=1, low=2) instead of the
enum's alphabetical string value. Requires importing `Priority` alongside the
existing `Task, TaskCreate` import at the top of `store.py`:

```python
from task_tracker_api.models import Priority, Task, TaskCreate
```

**Verification command**:

```
uv run pytest tests/test_main.py::test_tasks_sorted_by_priority_high_to_low -v
```

## Issue 3 — Admin bulk-delete endpoint: unsafe credential handling

**File**: `src/task_tracker_api/main.py`

**Before** (lines 1-21, relevant excerpt):

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

**After**:

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

Confirmed by testing in this environment: bare `uv run pytest` (not run
through `mise run test`) does NOT inherit `mise.toml`'s `[env]` block, so
`os.environ["ADMIN_API_KEY"]` (no default) would raise `KeyError` at import
time and break test collection for the entire suite. Use `.get(...)` with the
same non-secret local-dev default already committed in `mise.toml` (`
dev-local-admin-key-000`) as the fallback, so `uv run pytest` and `uv run
fastapi dev ...` both work unchanged whether or not `mise` injected the env
var, while production deployments are expected to set `ADMIN_API_KEY` for
real.

**Before** (lines 62-68, the handler):

```python
@app.delete("/admin/tasks", status_code=204)
def delete_all_tasks(x_admin_key: str = Header(...)) -> Response:
    if x_admin_key == ADMIN_API_KEY:
        clear_all()
        return Response(status_code=204)
    else:
        raise HTTPException(status_code=403, detail="Forbidden")
```

**After**:

```python
@app.delete("/admin/tasks", status_code=204)
def delete_all_tasks(x_admin_key: str = Header(...)) -> Response:
    if hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        clear_all()
        return Response(status_code=204)
    else:
        raise HTTPException(status_code=403, detail="Forbidden")
```

This addresses both facets identified in research: (1) the key is now sourced
from the `ADMIN_API_KEY` environment variable instead of a hardcoded literal
— `mise.toml` already sets a local-dev default (`ADMIN_API_KEY =
"dev-local-admin-key-000"` under `[env]`), so `mise run dev` keeps working
unchanged; (2) the comparison uses `hmac.compare_digest` (constant-time)
instead of `==`, removing the timing side-channel.

**Verification**: no automated test exists for this issue by design (see
`bug-context.md` Notes). Verify by reading the diff (hardcoded literal
removed, `hmac.compare_digest` used) and by manual curl checks if desired:

```
ADMIN_API_KEY=dev-local-admin-key-000 uv run fastapi dev src/task_tracker_api/main.py &
curl -i -X DELETE http://127.0.0.1:8000/admin/tasks -H "X-Admin-Key: dev-local-admin-key-000"   # expect 204
curl -i -X DELETE http://127.0.0.1:8000/admin/tasks -H "X-Admin-Key: wrong-key"                  # expect 403
```

## Final verification (after all three issues are fixed)

```
uv run pytest
```

All tests should pass.
