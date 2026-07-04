import pytest

from src.services import import_service


def csv_bytes(rows: str) -> bytes:
    header = "customer_id,customer_email,customer_name,subject,description,tags,metadata\n"
    return (header + rows).encode()


def test_parse_csv_valid_ticket() -> None:
    tickets, errors = import_service.parse_csv(
        csv_bytes('c1,a@example.com,Ada,Login issue,I cannot access my account,"login,password",\n')
    )

    assert len(tickets) == 1
    assert errors == []
    assert tickets[0].tags == ["login", "password"]


def test_parse_csv_accepts_json_tags_and_metadata() -> None:
    tickets, errors = import_service.parse_csv(
        csv_bytes(
            'c1,a@example.com,Ada,Login issue,I cannot access my account,"[""login""]",'
            '"{""source"":""email"",""browser"":""Chrome""}"\n'
        )
    )

    assert errors == []
    assert tickets[0].tags == ["login"]
    assert tickets[0].metadata is not None
    assert tickets[0].metadata.source == "email"


def test_parse_csv_reports_validation_error_with_row_number() -> None:
    tickets, errors = import_service.parse_csv(csv_bytes("c1,bad,Ada,Login issue,Too short,,\n"))

    assert tickets == []
    assert errors[0].row == 2
    assert "customer_email" in errors[0].error


def test_parse_csv_allows_partial_success() -> None:
    tickets, errors = import_service.parse_csv(
        csv_bytes(
            "c1,a@example.com,Ada,Login issue,I cannot access my account,,\nc2,bad,Bob,Short,No,,\n"
        )
    )

    assert len(tickets) == 1
    assert len(errors) == 1


def test_parse_csv_handles_utf8_bom() -> None:
    content = (
        "\ufeffcustomer_id,customer_email,customer_name,subject,description\n"
        "c1,a@example.com,Ada,Login issue,I cannot access my account\n"
    ).encode("utf-8")

    tickets, errors = import_service.parse_csv(content)

    assert len(tickets) == 1
    assert errors == []


def test_parse_csv_empty_file_returns_no_records() -> None:
    tickets, errors = import_service.parse_csv(b"")

    assert tickets == []
    assert errors == []


def test_parse_csv_invalid_utf8_raises_unicode_error() -> None:
    with pytest.raises(UnicodeDecodeError):
        import_service.parse_csv(b"\xff")
