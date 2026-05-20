from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from src.models.ticket import TicketCreate
from src.services import ticket_service

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_complete_ticket_lifecycle(client: TestClient, ticket_payload: dict) -> None:
    created = client.post("/tickets", json=ticket_payload)
    ticket_id = created.json()["id"]

    assert created.status_code == 201
    assert client.put(f"/tickets/{ticket_id}", json={"status": "in_progress"}).status_code == 200
    assert client.post(f"/tickets/{ticket_id}/auto-classify").status_code == 200
    assert client.delete(f"/tickets/{ticket_id}").status_code == 204
    assert client.get(f"/tickets/{ticket_id}").status_code == 404


def test_bulk_import_then_filter(client: TestClient) -> None:
    content = (
        "customer_id,customer_email,customer_name,subject,description,category,priority\n"
        "c1,a@example.com,Ada,Invoice question,"
        "Please explain duplicate charge,billing_question,low\n"
        "c2,b@example.com,Bob,Login issue,I cannot access my password reset,account_access,urgent\n"
    )

    imported = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", content, "text/csv")},
    )
    filtered = client.get("/tickets?category=account_access&priority=urgent")

    assert imported.json()["successful"] == 2
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["customer_id"] == "c2"


def test_bulk_import_with_auto_classification_verification(client: TestClient) -> None:
    content = (
        "customer_id,customer_email,customer_name,subject,description\n"
        "c1,a@example.com,Ada,Production down login,"
        "Critical login failure means users cannot access their account\n"
        "c2,b@example.com,Bob,Feature idea,"
        "Suggestion to please add a nice to have dashboard export\n"
    )

    imported = client.post(
        "/tickets/import?auto_classify=true",
        files={"file": ("tickets.csv", content, "text/csv")},
    )
    urgent = client.get("/tickets?category=account_access&priority=urgent").json()
    low = client.get("/tickets?category=feature_request&priority=low").json()

    assert imported.status_code == 200
    assert imported.json() == {"total": 2, "successful": 2, "failed": 0, "errors": []}
    assert len(urgent) == 1
    assert urgent[0]["classification_confidence"] is not None
    assert urgent[0]["classification_confidence"] > 0
    assert len(low) == 1
    assert low[0]["classification_confidence"] is not None


def test_bulk_import_with_partial_failure_keeps_valid_records(client: TestClient) -> None:
    content = """
    [
      {
        "customer_id": "c1",
        "customer_email": "a@example.com",
        "customer_name": "Ada",
        "subject": "Invoice question",
        "description": "Please explain duplicate charge"
      },
      {"customer_id": "bad"}
    ]
    """

    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.json", content, "application/json")},
    )

    assert response.json()["successful"] == 1
    assert response.json()["failed"] == 1
    assert len(client.get("/tickets").json()) == 1


def test_auto_classify_on_creation_then_manual_override(
    client: TestClient,
    minimal_ticket_payload: dict,
) -> None:
    created = client.post(
        "/tickets?auto_classify=true",
        json=minimal_ticket_payload
        | {
            "subject": "Refund request",
            "description": "I need a refund for a payment charge.",
        },
    ).json()

    updated = client.put(f"/tickets/{created['id']}", json={"priority": "low"})

    assert created["category"] == "billing_question"
    assert updated.status_code == 200
    assert updated.json()["priority"] == "low"


def test_concurrent_ticket_creation_20_plus_requests(
    client: TestClient,
    minimal_ticket_payload: dict,
) -> None:
    def create_ticket(index: int) -> int:
        payload = minimal_ticket_payload | {
            "customer_id": f"cust-{index}",
            "customer_email": f"user{index}@example.com",
        }
        ticket_service.create_ticket(TicketCreate.model_validate(payload))
        return 201

    with ThreadPoolExecutor(max_workers=5) as executor:
        statuses = list(executor.map(create_ticket, range(25)))

    assert statuses == [201] * 25
    assert len(client.get("/tickets").json()) == 25


def test_combined_filtering_by_category_and_priority(client: TestClient) -> None:
    sample_csv = (FIXTURES_DIR / "sample_tickets.csv").read_bytes()

    imported = client.post(
        "/tickets/import",
        files={"file": ("sample_tickets.csv", sample_csv, "text/csv")},
    )
    filtered = client.get("/tickets?category=account_access&priority=urgent")

    assert imported.status_code == 200
    assert imported.json()["successful"] == 50
    assert filtered.status_code == 200
    assert len(filtered.json()) == 9
    assert all(
        ticket["category"] == "account_access" and ticket["priority"] == "urgent"
        for ticket in filtered.json()
    )


def test_import_xml_end_to_end(client: TestClient) -> None:
    xml = """
    <tickets><ticket>
      <customer_id>c1</customer_id>
      <customer_email>a@example.com</customer_email>
      <customer_name>Ada</customer_name>
      <subject>Bug report</subject>
      <description>Steps to reproduce include actual behavior mismatch.</description>
      <category>bug_report</category>
      <priority>high</priority>
    </ticket></tickets>
    """

    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.xml", xml, "application/xml")},
    )

    assert response.status_code == 200
    assert response.json()["successful"] == 1
    assert client.get("/tickets?category=bug_report").json()[0]["priority"] == "high"
