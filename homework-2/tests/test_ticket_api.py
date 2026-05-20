from fastapi.testclient import TestClient


def test_create_ticket_returns_201(client: TestClient, ticket_payload: dict) -> None:
    response = client.post("/tickets", json=ticket_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["customer_email"] == "ada@example.com"
    assert body["tags"] == ["login", "password"]


def test_create_ticket_with_auto_classify(client: TestClient, minimal_ticket_payload: dict) -> None:
    payload = minimal_ticket_payload | {
        "subject": "Production down",
        "description": "Critical error means production down for every user.",
    }

    response = client.post("/tickets?auto_classify=true", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "technical_issue"
    assert body["priority"] == "urgent"
    assert body["classification_confidence"] is not None


def test_list_tickets_returns_created_ticket(client: TestClient, ticket_payload: dict) -> None:
    created = client.post("/tickets", json=ticket_payload).json()

    response = client.get("/tickets")

    assert response.status_code == 200
    assert [ticket["id"] for ticket in response.json()] == [created["id"]]


def test_list_tickets_filters_by_status_category_and_priority(
    client: TestClient,
    ticket_payload: dict,
    minimal_ticket_payload: dict,
) -> None:
    client.post("/tickets", json=ticket_payload)
    client.post(
        "/tickets",
        json=minimal_ticket_payload | {"category": "billing_question", "priority": "low"},
    )

    response = client.get("/tickets?status=new&category=account_access&priority=high")

    assert response.status_code == 200
    tickets = response.json()
    assert len(tickets) == 1
    assert tickets[0]["category"] == "account_access"


def test_get_ticket_by_id(client: TestClient, ticket_payload: dict) -> None:
    ticket_id = client.post("/tickets", json=ticket_payload).json()["id"]

    response = client.get(f"/tickets/{ticket_id}")

    assert response.status_code == 200
    assert response.json()["id"] == ticket_id


def test_get_missing_ticket_returns_404(client: TestClient) -> None:
    response = client.get("/tickets/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"


def test_update_ticket_partial_fields(client: TestClient, ticket_payload: dict) -> None:
    ticket_id = client.post("/tickets", json=ticket_payload).json()["id"]

    response = client.put(
        f"/tickets/{ticket_id}",
        json={"status": "in_progress", "assigned_to": "agent-2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["assigned_to"] == "agent-2"


def test_update_rejects_null_for_non_nullable_fields(
    client: TestClient, ticket_payload: dict
) -> None:
    ticket_id = client.post("/tickets", json=ticket_payload).json()["id"]

    for field in ("customer_id", "priority", "status", "tags"):
        response = client.put(f"/tickets/{ticket_id}", json={field: None})

        assert response.status_code == 422


def test_update_missing_ticket_returns_404(client: TestClient) -> None:
    response = client.put("/tickets/missing", json={"status": "closed"})

    assert response.status_code == 404


def test_update_resolved_sets_resolved_at(client: TestClient, ticket_payload: dict) -> None:
    ticket_id = client.post("/tickets", json=ticket_payload).json()["id"]

    response = client.put(f"/tickets/{ticket_id}", json={"status": "resolved"})

    assert response.status_code == 200
    assert response.json()["resolved_at"] is not None


def test_delete_ticket_returns_204_and_removes_ticket(
    client: TestClient, ticket_payload: dict
) -> None:
    ticket_id = client.post("/tickets", json=ticket_payload).json()["id"]

    response = client.delete(f"/tickets/{ticket_id}")

    assert response.status_code == 204
    assert client.get(f"/tickets/{ticket_id}").status_code == 404


def test_delete_missing_ticket_returns_404(client: TestClient) -> None:
    response = client.delete("/tickets/missing")

    assert response.status_code == 404


def test_create_invalid_ticket_returns_422(client: TestClient, ticket_payload: dict) -> None:
    response = client.post("/tickets", json=ticket_payload | {"customer_email": "not-email"})

    assert response.status_code == 422


def test_import_endpoint_accepts_csv_upload(client: TestClient) -> None:
    content = (
        "customer_id,customer_email,customer_name,subject,description,category,priority\n"
        "c1,a@example.com,Ada,Login problem,I cannot access my account now,account_access,urgent\n"
    )

    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", content, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json() == {"total": 1, "successful": 1, "failed": 0, "errors": []}
    assert len(client.get("/tickets").json()) == 1


def test_import_endpoint_rejects_unsupported_file_type(client: TestClient) -> None:
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.txt", "plain text", "text/plain")},
    )

    assert response.status_code == 415


def test_import_endpoint_returns_400_for_malformed_json(client: TestClient) -> None:
    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.json", "{bad", "application/json")},
    )

    assert response.status_code == 400
    assert "Invalid JSON" in response.json()["detail"]


def test_auto_classify_endpoint_updates_ticket(
    client: TestClient, minimal_ticket_payload: dict
) -> None:
    ticket_id = client.post("/tickets", json=minimal_ticket_payload).json()["id"]

    response = client.post(f"/tickets/{ticket_id}/auto-classify")

    assert response.status_code == 200
    assert response.json()["category"] == "billing_question"
    assert client.get(f"/tickets/{ticket_id}").json()["classification_confidence"] is not None


def test_auto_classify_missing_ticket_returns_404(client: TestClient) -> None:
    response = client.post("/tickets/missing/auto-classify")

    assert response.status_code == 404
