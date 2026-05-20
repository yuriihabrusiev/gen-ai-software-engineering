from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src import database
from src.main import app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db_path = tmp_path / "tickets.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()
    yield db_path


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def ticket_payload() -> dict:
    return {
        "customer_id": "cust-001",
        "customer_email": "ada@example.com",
        "customer_name": "Ada Lovelace",
        "subject": "Cannot access account",
        "description": "I cannot access my account after resetting my password.",
        "category": "account_access",
        "priority": "high",
        "status": "new",
        "assigned_to": "support-agent-1",
        "tags": ["login", "password"],
        "metadata": {
            "source": "web_form",
            "browser": "Firefox",
            "device_type": "desktop",
        },
    }


@pytest.fixture
def minimal_ticket_payload() -> dict:
    return {
        "customer_id": "cust-002",
        "customer_email": "grace@example.com",
        "customer_name": "Grace Hopper",
        "subject": "Billing question",
        "description": "Please explain the latest invoice charge.",
    }
