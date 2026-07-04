import pytest
from pydantic import ValidationError

from src.models.ticket import (
    Category,
    ClassificationResult,
    DeviceType,
    Priority,
    Source,
    Status,
    TicketCreate,
    TicketMetadata,
    TicketUpdate,
)


def valid_ticket_data() -> dict[str, object]:
    return {
        "customer_id": "cust-001",
        "customer_email": "ada@example.com",
        "customer_name": "Ada Lovelace",
        "subject": "Need support",
        "description": "This is a long enough ticket description.",
    }


def test_ticket_create_accepts_valid_minimal_data() -> None:
    ticket = TicketCreate.model_validate(valid_ticket_data())

    assert ticket.priority == Priority.medium
    assert ticket.status == Status.new
    assert ticket.category is None
    assert ticket.tags == []


def test_ticket_create_validates_email() -> None:
    with pytest.raises(ValidationError):
        TicketCreate.model_validate(valid_ticket_data() | {"customer_email": "bad"})


def test_ticket_create_validates_subject_length() -> None:
    with pytest.raises(ValidationError):
        TicketCreate.model_validate(valid_ticket_data() | {"subject": ""})


def test_ticket_create_validates_description_length() -> None:
    with pytest.raises(ValidationError):
        TicketCreate.model_validate(valid_ticket_data() | {"description": "short"})


def test_ticket_create_validates_category_enum() -> None:
    with pytest.raises(ValidationError):
        TicketCreate.model_validate(valid_ticket_data() | {"category": "bad_category"})


def test_ticket_metadata_accepts_source_and_device_type() -> None:
    metadata = TicketMetadata(source=Source.chat, browser="Safari", device_type=DeviceType.mobile)

    assert metadata.source == Source.chat
    assert metadata.device_type == DeviceType.mobile


def test_ticket_metadata_defaults_to_api_source() -> None:
    assert TicketMetadata().source == Source.api


def test_ticket_update_allows_partial_payload() -> None:
    update = TicketUpdate(status=Status.waiting_customer)

    assert update.status == Status.waiting_customer
    assert update.customer_email is None


def test_ticket_update_validates_optional_email_when_present() -> None:
    with pytest.raises(ValidationError):
        TicketUpdate(customer_email="invalid")


def test_classification_result_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        ClassificationResult(
            category=Category.other,
            priority=Priority.medium,
            confidence=1.1,
            reasoning="too high",
            keywords_found=[],
        )


def test_enum_values_match_api_contract() -> None:
    assert Category.account_access.value == "account_access"
    assert Priority.urgent.value == "urgent"
    assert Status.closed.value == "closed"
