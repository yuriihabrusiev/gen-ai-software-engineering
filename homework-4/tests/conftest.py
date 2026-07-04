import pytest
from fastapi.testclient import TestClient

from task_tracker_api import store
from task_tracker_api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    store.reset_store()
