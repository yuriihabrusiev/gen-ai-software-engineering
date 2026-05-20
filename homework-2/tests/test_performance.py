import json
import time

from fastapi.testclient import TestClient

from src.services import classification_service, import_service


def test_classifies_100_tickets_quickly() -> None:
    start = time.perf_counter()

    for _ in range(100):
        classification_service.classify("Production down", "Critical error blocks login access.")

    assert time.perf_counter() - start < 1.0


def test_parse_100_json_tickets_quickly() -> None:
    records = [
        {
            "customer_id": f"c{i}",
            "customer_email": f"user{i}@example.com",
            "customer_name": "Perf User",
            "subject": "Invoice question",
            "description": "Please explain the latest invoice charge.",
        }
        for i in range(100)
    ]

    start = time.perf_counter()
    tickets, errors = import_service.parse_json(json.dumps(records).encode())

    assert time.perf_counter() - start < 1.0
    assert len(tickets) == 100
    assert errors == []


def test_parse_100_csv_tickets_quickly() -> None:
    rows = ["customer_id,customer_email,customer_name,subject,description"]
    rows.extend(
        f"c{i},user{i}@example.com,Perf User,Login issue,I cannot access my account"
        for i in range(100)
    )

    start = time.perf_counter()
    tickets, errors = import_service.parse_csv(("\n".join(rows) + "\n").encode())

    assert time.perf_counter() - start < 1.0
    assert len(tickets) == 100
    assert errors == []


def test_create_50_tickets_quickly(client: TestClient, minimal_ticket_payload: dict) -> None:
    start = time.perf_counter()

    for i in range(50):
        payload = minimal_ticket_payload | {
            "customer_id": f"perf-{i}",
            "customer_email": f"perf{i}@example.com",
        }
        assert client.post("/tickets", json=payload).status_code == 201

    assert time.perf_counter() - start < 3.0


def test_list_50_tickets_quickly(client: TestClient, minimal_ticket_payload: dict) -> None:
    for i in range(50):
        payload = minimal_ticket_payload | {
            "customer_id": f"perf-{i}",
            "customer_email": f"perf{i}@example.com",
        }
        client.post("/tickets", json=payload)

    start = time.perf_counter()
    response = client.get("/tickets")

    assert time.perf_counter() - start < 1.0
    assert response.status_code == 200
    assert len(response.json()) == 50
