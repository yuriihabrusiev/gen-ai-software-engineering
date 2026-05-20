"""Parsers for CSV, JSON, and XML ticket import files."""

import csv
import io
import json
import xml.etree.ElementTree as ET
from typing import Any, cast

from pydantic import ValidationError

from src.models.ticket import ImportError, ImportSummary, TicketCreate


def _parse_row(raw: dict[str, Any], row_num: int) -> tuple[TicketCreate | None, ImportError | None]:
    """Validate a raw dict as a TicketCreate. Returns (ticket, None) or (None, error)."""
    # Coerce tags: accept comma-separated string or JSON array string
    if "tags" in raw and isinstance(raw["tags"], str):
        tags_str = raw["tags"].strip()
        if tags_str.startswith("["):
            try:
                raw["tags"] = json.loads(tags_str)
            except json.JSONDecodeError:
                raw["tags"] = [t.strip() for t in tags_str.strip("[]").split(",") if t.strip()]
        else:
            raw["tags"] = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    # Coerce metadata: accept JSON string
    if "metadata" in raw and isinstance(raw["metadata"], str):
        meta_str = raw["metadata"].strip()
        if meta_str:
            try:
                raw["metadata"] = json.loads(meta_str)
            except json.JSONDecodeError:
                raw["metadata"] = None
        else:
            raw["metadata"] = None

    try:
        ticket = TicketCreate(**raw)
        return ticket, None
    except ValidationError as exc:
        messages = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return None, ImportError(row=row_num, error=messages)
    except Exception as exc:  # noqa: BLE001
        return None, ImportError(row=row_num, error=str(exc))


def parse_csv(content: bytes) -> tuple[list[TicketCreate], list[ImportError]]:
    tickets: list[TicketCreate] = []
    errors: list[ImportError] = []

    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    for row_num, row in enumerate(reader, start=2):  # row 1 = header
        raw = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k}
        ticket, error = _parse_row(raw, row_num)
        if ticket:
            tickets.append(ticket)
        else:
            assert error is not None
            errors.append(error)

    return tickets, errors


def parse_json(content: bytes) -> tuple[list[TicketCreate], list[ImportError]]:
    tickets: list[TicketCreate] = []
    errors: list[ImportError] = []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("JSON root must be an array of ticket objects")

    for row_num, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            errors.append(ImportError(row=row_num, error="Each item must be a JSON object"))
            continue
        ticket, error = _parse_row(cast(dict[str, Any], item), row_num)
        if ticket:
            tickets.append(ticket)
        else:
            assert error is not None
            errors.append(error)

    return tickets, errors


def _elem_to_dict(elem: ET.Element) -> dict[str, Any]:
    """Convert a <ticket> XML element to a flat dict, with nested <metadata> and <tags>."""
    result: dict[str, Any] = {}
    for child in elem:
        if child.tag == "tags":
            result["tags"] = [tag.text for tag in child if tag.text]
        elif child.tag == "metadata":
            meta: dict[str, str] = {}
            for meta_child in child:
                if meta_child.text:
                    meta[meta_child.tag] = meta_child.text
            result["metadata"] = meta if meta else None
        else:
            result[child.tag] = child.text
    return result


def parse_xml(content: bytes) -> tuple[list[TicketCreate], list[ImportError]]:
    tickets: list[TicketCreate] = []
    errors: list[ImportError] = []

    try:
        root = ET.fromstring(content)  # noqa: S314
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML: {exc}") from exc

    # Accept <tickets> root or bare <ticket> list
    ticket_elems = root.findall("ticket") if root.tag != "ticket" else [root]

    for row_num, elem in enumerate(ticket_elems, start=1):
        raw = _elem_to_dict(elem)
        ticket, error = _parse_row(raw, row_num)
        if ticket:
            tickets.append(ticket)
        else:
            assert error is not None
            errors.append(error)

    return tickets, errors


def build_summary(
    tickets: list[TicketCreate],
    errors: list[ImportError],
) -> ImportSummary:
    return ImportSummary(
        total=len(tickets) + len(errors),
        successful=len(tickets),
        failed=len(errors),
        errors=errors,
    )
