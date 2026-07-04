import json

import pytest

from src.services import import_service


def valid_json_ticket(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "customer_id": "c1",
        "customer_email": "a@example.com",
        "customer_name": "Ada",
        "subject": "Invoice question",
        "description": "Please explain my invoice and recent charge.",
        "tags": ["billing"],
        "metadata": {"source": "email", "device_type": "desktop"},
    }
    data.update(overrides)
    return data


def test_parse_json_valid_array() -> None:
    tickets, errors = import_service.parse_json(json.dumps([valid_json_ticket()]).encode())

    assert len(tickets) == 1
    assert errors == []
    assert tickets[0].metadata is not None


def test_parse_json_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match="Invalid JSON"):
        import_service.parse_json(b"{bad")


def test_parse_json_requires_array_root() -> None:
    with pytest.raises(ValueError, match="JSON root must be an array"):
        import_service.parse_json(json.dumps(valid_json_ticket()).encode())


def test_parse_json_reports_non_object_items() -> None:
    tickets, errors = import_service.parse_json(json.dumps(["bad"]).encode())

    assert tickets == []
    assert errors[0].error == "Each item must be a JSON object"


def test_parse_json_allows_partial_success() -> None:
    tickets, errors = import_service.parse_json(
        json.dumps([valid_json_ticket(), valid_json_ticket(customer_email="bad")]).encode()
    )

    assert len(tickets) == 1
    assert len(errors) == 1


def test_parse_json_accepts_string_tags_and_metadata() -> None:
    tickets, errors = import_service.parse_json(
        json.dumps(
            [
                valid_json_ticket(
                    tags="billing,invoice",
                    metadata=json.dumps({"source": "chat", "browser": "Edge"}),
                )
            ]
        ).encode()
    )

    assert errors == []
    assert tickets[0].tags == ["billing", "invoice"]
    assert tickets[0].metadata is not None
    assert tickets[0].metadata.source == "chat"
