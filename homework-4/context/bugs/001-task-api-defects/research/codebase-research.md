# Codebase Research: 001-task-api-defects

Three independent, unrelated defects in the Task Tracker API. Each is documented
separately below with exact file:line references and verbatim source snippets.

## Issue 1 — Stats endpoint crashes when there are no tasks

**Root cause location**: `src/task_tracker_api/store.py:65-74`, function `stats()`.

```python
65	def stats() -> dict:
66	    total = len(tasks)
67	    completed_count = sum(1 for task in tasks.values() if task.completed)
68	    # SEEDED BUG: no guard for total == 0, raises ZeroDivisionError.
69	    percent_complete = round(completed_count / total * 100, 1)
70	    return {
71	        "total": total,
72	        "completed": completed_count,
73	        "percent_complete": percent_complete,
74	    }
```

`total` is `len(tasks)` (`store.py:66`). When the in-memory `tasks` dict
(`store.py:3`) is empty, `total == 0`, and line 69 computes
`completed_count / total * 100`, i.e. `0 / 0 * 100`, which raises
`ZeroDivisionError` in Python. This propagates out of the `GET /tasks/stats`
route handler:

```python
34	@app.get("/tasks/stats")
35	def get_stats() -> dict:
36	    return stats()
```

(`src/task_tracker_api/main.py:34-36`) — the handler does no error handling, so
FastAPI's default exception handling turns the unhandled `ZeroDivisionError`
into an HTTP 500 response, matching the reported "Actual" behavior.

The comment on line 68 (`# SEEDED BUG: no guard for total == 0, raises
ZeroDivisionError.`) confirms this is the intended defect.

**Fix direction**: guard the division — when `total == 0`, `percent_complete`
should be `0` (matching the bug report's expected body
`{"total": 0, "completed": 0, "percent_complete": 0}` and the pinned test
`test_stats_with_no_tasks_returns_zero_percent` at `tests/test_main.py:53-57`,
which only asserts `body["percent_complete"] == 0` and a `200` status).

## Issue 2 — Priority sort returns the wrong order

**Root cause location**: `src/task_tracker_api/store.py:22-33`, function `list_tasks()`.

```python
22	def list_tasks(completed: bool | None = None, sort: str | None = None) -> list[Task]:
23	    results = list(tasks.values())
24	
25	    if completed is not None:
26	        results = [task for task in results if task.completed == completed]
27	
28	    if sort == "priority":
29	        # SEEDED BUG: plain alphabetical sort on the enum value gives
30	        # high, low, medium — not the correct severity order.
31	        results = sorted(results, key=lambda t: t.priority.value)
32	
33	    return results
```

`Task.priority` is a `Priority` `StrEnum` (`src/task_tracker_api/models.py:7-10`):

```python
7	class Priority(StrEnum):
8	    LOW = "low"
9	    MEDIUM = "medium"
10	    HIGH = "high"
```

Because `Priority` is a `StrEnum`, `t.priority.value` is the literal string
`"low"`, `"medium"`, or `"high"`. Sorting by that string alphabetically
(`store.py:31`) yields `"high" < "low" < "medium"` lexicographically, i.e.
order `high, low, medium` — exactly the "Actual" order reported in the bug
context (`bug-context.md:44`), not the desired severity order
`high, medium, low`.

This is reached via the route handler at `src/task_tracker_api/main.py:29-31`:

```python
29	@app.get("/tasks", response_model=list[Task])
30	def get_tasks(completed: bool | None = None, sort: str | None = None) -> list[Task]:
31	    return list_tasks(completed=completed, sort=sort)
```

which just forwards `sort` straight to `list_tasks` — the route itself is not
buggy, consistent with the bug context's note that `main.py` "just wires the
two `store.py` functions above to their routes."

The comment on lines 29-30 confirms this is the intended defect.

**Fix direction**: sort by severity rank rather than alphabetical string value,
e.g. a rank mapping `{Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}`
(descending severity), matching the pinned test
`test_tasks_sorted_by_priority_high_to_low` at `tests/test_main.py:60-68`,
which asserts the returned order is `["high", "medium", "low"]`.

## Issue 3 — Admin bulk-delete endpoint: unsafe credential handling

**Root cause location**: `src/task_tracker_api/main.py:20-21` (key definition)
and `main.py:62-68` (the route handler that checks it).

```python
20	# SEEDED SECURITY ISSUE: hardcoded admin key checked with plain equality.
21	ADMIN_API_KEY = "supersecret-admin-key-123"
```

```python
62	@app.delete("/admin/tasks", status_code=204)
63	def delete_all_tasks(x_admin_key: str = Header(...)) -> Response:
64	    if x_admin_key == ADMIN_API_KEY:
65	        clear_all()
66	        return Response(status_code=204)
67	    else:
68	        raise HTTPException(status_code=403, detail="Forbidden")
```

Two distinct security problems are present, both flagged by the seeded-bug
comment on line 20:

1. **Hardcoded secret in source code** (`main.py:21`). The admin key is a
   plaintext literal committed to version control, rather than being read
   from configuration/environment. Anyone with source access (or the public
   repo, or a leaked build artifact) has the admin credential permanently,
   and rotating it requires a code change and redeploy. `mise.toml` (repo
   root) already defines a local-dev-appropriate mechanism for this:

   ```toml
   [env]
   ADMIN_API_KEY = "dev-local-admin-key-000"
   ```

   confirming that `mise run dev` expects the app to read `ADMIN_API_KEY`
   from the environment. `main.py` presently ignores this environment
   variable entirely and uses the hardcoded literal instead.

2. **Non-constant-time comparison** (`main.py:64`, `x_admin_key ==
   ADMIN_API_KEY`). Python's `==` on strings short-circuits on the first
   differing byte, so comparison time leaks information about how many
   leading characters of a guessed key are correct. This makes the check
   theoretically vulnerable to a timing side-channel attack that could speed
   up brute-forcing the admin key, versus a constant-time comparison such as
   `hmac.compare_digest`.

There is intentionally no automated functional test for this issue (per
`bug-context.md:86-89`): the endpoint behaves identically (returns 204 for the
correct key, 403 otherwise) whether the key is hardcoded or
environment-sourced, and whether the comparison is `==` or
`hmac.compare_digest`. Only source inspection reveals the defect, which is
what the dedicated security-review pipeline stage is for.

**Fix direction**: read `ADMIN_API_KEY` from the environment (e.g. via
`os.environ["ADMIN_API_KEY"]` at module load, or `os.environ.get(...)` with a
safe fallback for tests) instead of the hardcoded literal, and compare using
`hmac.compare_digest` instead of `==`.

## Summary of files to change

| Issue | File | Function/lines |
|---|---|---|
| 1 | `src/task_tracker_api/store.py` | `stats()`, lines 65-74 |
| 2 | `src/task_tracker_api/store.py` | `list_tasks()`, lines 22-33 |
| 3 | `src/task_tracker_api/main.py` | `ADMIN_API_KEY` (line 21) and `delete_all_tasks()` (lines 62-68) |

`tests/test_main.py` requires no changes — it already pins the correct
expected behavior for issues 1 and 2 (lines 53-57 and 60-68 respectively), and
has no test for issue 3 by design.
