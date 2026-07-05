# Test Report: 001-task-api-defects

## Summary

Five new FIRST-compliant unit tests were written for Issue 3 (the admin bulk-delete endpoint with HMAC-based credential handling). Issues 1 and 2 already had passing tests in tests/test_main.py. All 12 tests (7 original + 5 new) pass successfully.

## Changed Units Covered

| Function/File | Change | Test Coverage |
|---|---|---|
| `src/task_tracker_api/main.py` — `delete_all_tasks()` endpoint | Added environment-based ADMIN_API_KEY sourcing (with fallback default) and HMAC-based comparison instead of plain `==`. | 5 new tests covering success case (204), wrong key rejection (403), missing header validation (422), and explicit verification that `hmac.compare_digest` is used for comparison (via mocking). |
| `src/task_tracker_api/main.py` — ADMIN_API_KEY constant | Changed from hardcoded `"supersecret-admin-key-123"` to `os.environ.get("ADMIN_API_KEY", "dev-local-admin-key-000")`. | Implicitly tested via all 5 admin endpoint tests (they use the default key). |

## Test Files

- **tests/test_main.py** — Modified to add 5 new tests for the DELETE /admin/tasks endpoint (lines 76–170).

## FIRST Compliance

The `unit-tests-first` skill was explicitly consulted and applied to each of the 5 new tests:

### test_admin_delete_all_tasks_with_correct_key_clears_store
- **Fast**: No external I/O or network calls; uses TestClient with in-memory store (automatically cleared by `_reset_store` fixture before each test).
- **Independent**: Each test gets a fresh, isolated store via the autouse `_reset_store` fixture; no shared state with other tests.
- **Repeatable**: No time-dependent logic, randomness, or state carried over between runs. The key is a constant; tasks are predictable.
- **Self-validating**: Asserts specific HTTP 204 status, verifies task list is empty after deletion (len == 0), and verifies 2 tasks existed before (specific counts).
- **Timely**: Tests only the exact fix from Issue 3 — the new behavior of the DELETE /admin/tasks endpoint with correct credentials. No unrelated code.

### test_admin_delete_all_tasks_with_wrong_key_returns_403
- **Fast**: TestClient, in-memory store; no real network or I/O.
- **Independent**: Fresh store per test via `_reset_store` fixture; no interaction with other tests.
- **Repeatable**: Fixed key values; no randomness or time dependence.
- **Self-validating**: Asserts exact status code 403, exact error response body `{"detail": "Forbidden"}`, and verifies the task was not deleted (count remains 1).
- **Timely**: Tests the rejection case of Issue 3 — the new HMAC-based credential check that rejects incorrect keys.

### test_admin_delete_all_tasks_missing_header_returns_422
- **Fast**: TestClient, in-memory store.
- **Independent**: Fresh store per test via fixture.
- **Repeatable**: No external dependencies; omitting the header is deterministic.
- **Self-validating**: Asserts exact status code 422 (validation error) and verifies the task was not deleted (count remains 1).
- **Timely**: Tests the edge case of a missing required header — validates that FastAPI correctly enforces the X-Admin-Key header requirement.

### test_admin_delete_all_tasks_uses_hmac_compare_digest
- **Fast**: Uses `unittest.mock.patch` to replace `hmac.compare_digest` with a mock object; no real cryptographic calls.
- **Independent**: Mock is scoped to this single test via the decorator; no global state. Fresh store via `_reset_store`.
- **Repeatable**: Mock return value is deterministic; no randomness or clock dependence.
- **Self-validating**: Asserts that `hmac.compare_digest` was called exactly once with the expected arguments (both ADMIN_API_KEY in this case, since the mock short-circuits before the actual function). Also asserts the response is 204 as expected.
- **Timely**: Directly tests Issue 3's security fix — verifies that `hmac.compare_digest` is being invoked, not a string equality check.

### test_admin_delete_all_tasks_hmac_compare_digest_false_returns_403
- **Fast**: Mock-based; no real crypto or I/O.
- **Independent**: Mock is isolated to this test; fresh store via `_reset_store`.
- **Repeatable**: Mock behavior is fixed; deterministic outcome.
- **Self-validating**: Asserts that when `hmac.compare_digest` returns False, the response is 403 with the correct error detail. Confirms the endpoint correctly handles the false case.
- **Timely**: Tests the integration of `hmac.compare_digest` in the rejection logic — ensures the endpoint uses the result correctly.

All five tests follow the project's existing conventions (pytest, FastAPI TestClient, conftest-provided fixtures, Arrange-Act-Assert structure, explicit assertions on status codes and response bodies).

## Test Run

**Command**:
```
uv run pytest tests/test_main.py -v
```

**Results** (from actual run):
```
============================= test session starts ==============================
tests/test_main.py::test_create_and_get_task PASSED                      [  8%]
tests/test_main.py::test_list_tasks_filter_by_completed PASSED           [ 16%]
tests/test_main.py::test_mark_task_completed PASSED                      [ 25%]
tests/test_main.py::test_delete_task_then_404_on_refetch PASSED          [ 33%]
tests/test_main.py::test_404_on_nonexistent_task PASSED                  [ 41%]
tests/test_main.py::test_stats_with_no_tasks_returns_zero_percent PASSED [ 50%]
tests/test_main.py::test_tasks_sorted_by_priority_high_to_low PASSED     [ 58%]
tests/test_main.py::test_admin_delete_all_tasks_with_correct_key_clears_store PASSED [ 66%]
tests/test_main.py::test_admin_delete_all_tasks_with_wrong_key_returns_403 PASSED [ 75%]
tests/test_main.py::test_admin_delete_all_tasks_missing_header_returns_422 PASSED [ 83%]
tests/test_main.py::test_admin_delete_all_tasks_uses_hmac_compare_digest PASSED [ 91%]
tests/test_main.py::test_admin_delete_all_tasks_hmac_compare_digest_false_returns_403 PASSED [100%]

======================== 12 passed, 1 warning in 0.07s =========================
```

**Full test suite**:
```
uv run pytest
======================== 12 passed, 1 warning in 0.06s =========================
```

All tests pass. No failures, no skips.

## Test Cases Detail

The five new tests comprehensively cover Issue 3:

1. **Correct key succeeds (HTTP 204)**: Verifies that when the correct admin key is provided via the X-Admin-Key header, the endpoint returns 204 No Content and the task store is cleared.

2. **Wrong key rejected (HTTP 403)**: Verifies that when an incorrect key is provided, the endpoint returns 403 Forbidden with the expected error message, and the store is not cleared.

3. **Missing header validation (HTTP 422)**: Verifies that omitting the required X-Admin-Key header results in a 422 Unprocessable Entity response (FastAPI's built-in validation), and the store is not cleared.

4. **HMAC usage verification**: Uses `unittest.mock.patch` to mock `hmac.compare_digest` and asserts that it is called with the provided key and the ADMIN_API_KEY constant. This regression test ensures the code is not using plain string equality (`==`).

5. **HMAC false case**: Verifies that when `hmac.compare_digest` returns False, the endpoint correctly returns 403. This tests the integration of the HMAC result into the endpoint logic.

## References

### Changed Files
- **src/task_tracker_api/main.py** (lines 1–23, 64–70):
  - Imports `hmac` and `os` (line 1–2).
  - ADMIN_API_KEY now sourced from `os.environ.get("ADMIN_API_KEY", "dev-local-admin-key-000")` (line 23).
  - `delete_all_tasks()` handler uses `hmac.compare_digest(x_admin_key, ADMIN_API_KEY)` instead of `x_admin_key == ADMIN_API_KEY` (line 66).

### Test File
- **tests/test_main.py** (lines 1–6, 76–170):
  - Imported `unittest.mock` and `pytest` for mocking and assertions.
  - Imported `ADMIN_API_KEY` from `task_tracker_api.main` for use in tests.
  - Added 5 new test functions covering the DELETE /admin/tasks endpoint.

### Related Documentation
- fix-summary.md (Issue 3 section, lines 94–175)
