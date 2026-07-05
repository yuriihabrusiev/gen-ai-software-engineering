# Bug Context: 001-task-api-defects

## Summary

The Task Tracker API (`src/task_tracker_api/`) has three independent, unrelated defects
seeded for this pipeline run — two functional bugs and one security issue. They live in
different functions and can be fixed in any order.

1. **Stats endpoint crashes when there are no tasks.** `GET /tasks/stats` returns
   HTTP 500 instead of a normal response when the task list is empty.
2. **Priority sort returns the wrong order.** `GET /tasks?sort=priority` does not return
   results ordered from highest to lowest severity.
3. **Security: the admin bulk-delete endpoint's credential handling is unsafe.**
   `DELETE /admin/tasks` is guarded by a key, but the way that key is stored and checked
   does not meet basic security practice.

## Reproduction

Start the app first: `mise run dev` (or `uv run fastapi dev src/task_tracker_api/main.py`),
serving on `http://127.0.0.1:8000`.

### Issue 1 — stats crash

```bash
curl -i http://127.0.0.1:8000/tasks/stats
```

- **Expected**: `200 OK` with a body like `{"total": 0, "completed": 0, "percent_complete": 0}`.
- **Actual**: `500 Internal Server Error` when no tasks have been created yet.

Automated repro: `uv run pytest tests/test_main.py::test_stats_with_no_tasks_returns_zero_percent -v`
(currently fails).

### Issue 2 — wrong sort order

```bash
curl -X POST http://127.0.0.1:8000/tasks -H 'Content-Type: application/json' -d '{"title":"a","priority":"low"}'
curl -X POST http://127.0.0.1:8000/tasks -H 'Content-Type: application/json' -d '{"title":"b","priority":"high"}'
curl -X POST http://127.0.0.1:8000/tasks -H 'Content-Type: application/json' -d '{"title":"c","priority":"medium"}'
curl "http://127.0.0.1:8000/tasks?sort=priority"
```

- **Expected**: tasks ordered `high, medium, low`.
- **Actual**: tasks ordered `high, low, medium`.

Automated repro: `uv run pytest tests/test_main.py::test_tasks_sorted_by_priority_high_to_low -v`
(currently fails).

### Issue 3 — admin endpoint credential handling

```bash
curl -X DELETE http://127.0.0.1:8000/admin/tasks -H "X-Admin-Key: supersecret-admin-key-123"
```

This currently succeeds (204) with that specific key. That the endpoint *works* is not
the problem — inspect how the app defines and checks the admin key in
`src/task_tracker_api/main.py`. There is no automated test for this one (see Notes) —
it requires reading the source, not just exercising the endpoint.

## Affected Area

- `src/task_tracker_api/store.py` — contains the logic behind issues 1 and 2 (the
  `stats()` and `list_tasks()` functions).
- `src/task_tracker_api/main.py` — contains the logic behind issue 3 (the admin-key
  definition and the `DELETE /admin/tasks` handler). Also just wires the two `store.py`
  functions above to their routes; the routes themselves are not buggy.
- `tests/test_main.py` — existing test suite; two tests here already pin the expected
  (correct) behavior for issues 1 and 2 and currently fail against the live bugs.

## Verification Commands

Because these are three **independent** issues in one bug case, verify each one with a
scoped test after its specific fix, and only run the full suite once as a final check —
running the full suite after each individual fix will show unrelated, not-yet-fixed
issues as failures and should not be treated as a regression in the fix you just made.

- After fixing issue 1: `uv run pytest tests/test_main.py::test_stats_with_no_tasks_returns_zero_percent -v`
- After fixing issue 2: `uv run pytest tests/test_main.py::test_tasks_sorted_by_priority_high_to_low -v`
- After all fixes are applied: `uv run pytest` (full suite; all tests should pass)

## Notes

- These are 3 independent issues bundled into one bug case so a single pipeline run can
  resolve all of them together (the security fix in particular needs to land in the same
  change set the Security Verifier will review — it cannot fix anything itself).
- Issue 3 (the security issue) intentionally has **no failing automated test** — the
  admin endpoint behaves correctly for both valid and invalid keys either way, so no
  functional test would ever catch it. It can only be found by reading the code, which is
  exactly what the dedicated security-review stage of this pipeline is for.
- If issue 3 is fixed by making the admin key configurable via an environment variable,
  `mise.toml` already defines a local-dev default under `[env] ADMIN_API_KEY`, so
  `mise run dev` keeps working without any further setup.
