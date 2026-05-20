import pytest

from src.services import import_service

VALID_TICKET_XML = """
<ticket>
  <customer_id>c1</customer_id>
  <customer_email>a@example.com</customer_email>
  <customer_name>Ada</customer_name>
  <subject>Feature request</subject>
  <description>Please add support for exporting invoices.</description>
  <tags><tag>feature</tag><tag>export</tag></tags>
  <metadata><source>web_form</source><device_type>desktop</device_type></metadata>
</ticket>
"""


def test_parse_xml_valid_tickets_root() -> None:
    tickets, errors = import_service.parse_xml(f"<tickets>{VALID_TICKET_XML}</tickets>".encode())

    assert len(tickets) == 1
    assert errors == []
    assert tickets[0].tags == ["feature", "export"]


def test_parse_xml_valid_single_ticket_root() -> None:
    tickets, errors = import_service.parse_xml(VALID_TICKET_XML.encode())

    assert len(tickets) == 1
    assert errors == []


def test_parse_xml_rejects_malformed_xml() -> None:
    with pytest.raises(ValueError, match="Invalid XML"):
        import_service.parse_xml(b"<tickets><ticket></tickets>")


def test_parse_xml_reports_validation_error() -> None:
    xml = """
    <tickets><ticket>
      <customer_id>c1</customer_id>
      <customer_email>bad</customer_email>
      <customer_name>Ada</customer_name>
      <subject>Bad</subject>
      <description>short</description>
    </ticket></tickets>
    """

    tickets, errors = import_service.parse_xml(xml.encode())

    assert tickets == []
    assert errors[0].row == 1
    assert "customer_email" in errors[0].error


def test_parse_xml_allows_partial_success() -> None:
    xml = f"""
    <tickets>
      {VALID_TICKET_XML}
      <ticket><customer_id>c2</customer_id></ticket>
    </tickets>
    """

    tickets, errors = import_service.parse_xml(xml.encode())

    assert len(tickets) == 1
    assert len(errors) == 1


def test_parse_xml_empty_wrapper_returns_no_records() -> None:
    tickets, errors = import_service.parse_xml(b"<tickets></tickets>")

    assert tickets == []
    assert errors == []
