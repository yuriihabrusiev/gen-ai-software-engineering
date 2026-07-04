from unittest import mock

import pytest
from fastapi.testclient import TestClient

from task_tracker_api.main import ADMIN_API_KEY


def test_create_and_get_task(client: TestClient) -> None:
    create_response = client.post("/tasks", json={"title": "Buy milk"})
    assert create_response.status_code == 201
    task = create_response.json()

    get_response = client.get(f"/tasks/{task['id']}")
    assert get_response.status_code == 200
    assert get_response.json() == task


def test_list_tasks_filter_by_completed(client: TestClient) -> None:
    first = client.post("/tasks", json={"title": "Task A"}).json()
    client.post("/tasks", json={"title": "Task B"})
    client.patch(f"/tasks/{first['id']}/complete")

    completed_response = client.get("/tasks", params={"completed": True})
    assert completed_response.status_code == 200
    completed_tasks = completed_response.json()
    assert len(completed_tasks) == 1
    assert completed_tasks[0]["id"] == first["id"]

    incomplete_response = client.get("/tasks", params={"completed": False})
    assert len(incomplete_response.json()) == 1


def test_mark_task_completed(client: TestClient) -> None:
    task = client.post("/tasks", json={"title": "Task"}).json()

    response = client.patch(f"/tasks/{task['id']}/complete")
    assert response.status_code == 200
    assert response.json()["completed"] is True


def test_delete_task_then_404_on_refetch(client: TestClient) -> None:
    task = client.post("/tasks", json={"title": "Task"}).json()

    delete_response = client.delete(f"/tasks/{task['id']}")
    assert delete_response.status_code == 204

    get_response = client.get(f"/tasks/{task['id']}")
    assert get_response.status_code == 404


def test_404_on_nonexistent_task(client: TestClient) -> None:
    assert client.get("/tasks/999").status_code == 404
    assert client.patch("/tasks/999/complete").status_code == 404
    assert client.delete("/tasks/999").status_code == 404


def test_stats_with_no_tasks_returns_zero_percent(client: TestClient) -> None:
    response = client.get("/tasks/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["percent_complete"] == 0


def test_tasks_sorted_by_priority_high_to_low(client: TestClient) -> None:
    client.post("/tasks", json={"title": "Low task", "priority": "low"})
    client.post("/tasks", json={"title": "High task", "priority": "high"})
    client.post("/tasks", json={"title": "Medium task", "priority": "medium"})

    response = client.get("/tasks", params={"sort": "priority"})
    assert response.status_code == 200
    priorities = [task["priority"] for task in response.json()]
    assert priorities == ["high", "medium", "low"]


def test_admin_delete_all_tasks_with_correct_key_clears_store(
    client: TestClient,
) -> None:
    """Test that the admin endpoint clears all tasks and returns 204 with correct key."""
    # Arrange: create some tasks
    client.post("/tasks", json={"title": "Task 1"})
    client.post("/tasks", json={"title": "Task 2"})
    tasks_before = client.get("/tasks").json()
    assert len(tasks_before) == 2

    # Act: call admin delete with correct key
    response = client.delete(
        "/admin/tasks", headers={"X-Admin-Key": ADMIN_API_KEY}
    )

    # Assert: returns 204 and tasks are cleared
    assert response.status_code == 204
    tasks_after = client.get("/tasks").json()
    assert len(tasks_after) == 0


def test_admin_delete_all_tasks_with_wrong_key_returns_403(
    client: TestClient,
) -> None:
    """Test that the admin endpoint returns 403 Forbidden with incorrect key."""
    # Arrange: create a task
    client.post("/tasks", json={"title": "Task"})
    tasks_before = client.get("/tasks").json()
    assert len(tasks_before) == 1

    # Act: call admin delete with wrong key
    response = client.delete(
        "/admin/tasks", headers={"X-Admin-Key": "wrong-key-12345"}
    )

    # Assert: returns 403 and tasks are not cleared
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
    tasks_after = client.get("/tasks").json()
    assert len(tasks_after) == 1


def test_admin_delete_all_tasks_missing_header_returns_422(
    client: TestClient,
) -> None:
    """Test that the admin endpoint requires the X-Admin-Key header."""
    # Arrange: create a task
    client.post("/tasks", json={"title": "Task"})
    tasks_before = client.get("/tasks").json()
    assert len(tasks_before) == 1

    # Act: call admin delete without the required header
    response = client.delete("/admin/tasks")

    # Assert: returns 422 (validation error) and tasks are not cleared
    assert response.status_code == 422
    tasks_after = client.get("/tasks").json()
    assert len(tasks_after) == 1


@mock.patch("task_tracker_api.main.hmac.compare_digest")
def test_admin_delete_all_tasks_uses_hmac_compare_digest(
    mock_compare_digest: mock.Mock, client: TestClient
) -> None:
    """Test that the admin endpoint uses hmac.compare_digest for key comparison."""
    # Arrange: configure the mock to return True for the correct key
    mock_compare_digest.return_value = True

    # Act: call admin delete with a key
    response = client.delete(
        "/admin/tasks", headers={"X-Admin-Key": ADMIN_API_KEY}
    )

    # Assert: hmac.compare_digest was called with both the provided key and ADMIN_API_KEY
    assert response.status_code == 204
    mock_compare_digest.assert_called_once_with(ADMIN_API_KEY, ADMIN_API_KEY)


@mock.patch("task_tracker_api.main.hmac.compare_digest")
def test_admin_delete_all_tasks_hmac_compare_digest_false_returns_403(
    mock_compare_digest: mock.Mock, client: TestClient
) -> None:
    """Test that returning False from hmac.compare_digest results in 403."""
    # Arrange: configure the mock to return False
    mock_compare_digest.return_value = False

    # Act: call admin delete with a key
    response = client.delete(
        "/admin/tasks", headers={"X-Admin-Key": "some-key"}
    )

    # Assert: returns 403 Forbidden
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
