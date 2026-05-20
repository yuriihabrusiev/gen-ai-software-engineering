from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient


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

    updated = client.put(created["id"].join(["/tickets/", ""]), json={"priority": "low"})

    assert created["category"] == "billing_question"
    assert updated.status_code == 200
    assert updated.json()["priority"] == "low"


def test_concurrent_ticket_creation(client: TestClient, minimal_ticket_payload: dict) -> None:
    def create_ticket(index: int) -> int:
        payload = minimal_ticket_payload | {
            "customer_id": f"cust-{index}",
            "customer_email": f"user{index}@example.com",
        }
        return client.post("/tickets", json=payload).status_code

    with ThreadPoolExecutor(max_workers=5) as executor:
        statuses = list(executor.map(create_ticket, range(20)))

    assert statuses == [201] * 20
    assert len(client.get("/tickets").json()) == 20


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
