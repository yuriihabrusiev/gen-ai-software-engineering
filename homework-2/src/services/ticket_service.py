import json
import uuid
from datetime import UTC, datetime

from src.database import get_conn, row_to_dict
from src.models.ticket import (
    ClassificationResult,
    Status,
    TicketCreate,
    TicketResponse,
    TicketUpdate,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_ticket(data: TicketCreate) -> TicketResponse:
    ticket_id = str(uuid.uuid4())
    now = _now()
    metadata_json = data.metadata.model_dump_json() if data.metadata else None

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO tickets
                (id, customer_id, customer_email, customer_name, subject, description,
                 category, priority, status, created_at, updated_at,
                 resolved_at, assigned_to, tags, metadata)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                data.customer_id,
                str(data.customer_email),
                data.customer_name,
                data.subject,
                data.description,
                data.category.value if data.category else None,
                data.priority.value,
                data.status.value,
                now,
                now,
                None,
                data.assigned_to,
                json.dumps(data.tags),
                metadata_json,
            ),
        )

    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise RuntimeError(f"Inserted ticket {ticket_id} could not be fetched")
    return ticket


def get_ticket(ticket_id: str) -> TicketResponse | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()

    if row is None:
        return None
    return TicketResponse(**row_to_dict(row))


def list_tickets(
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
) -> list[TicketResponse]:
    query = "SELECT * FROM tickets WHERE 1=1"
    params: list[str] = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    if priority:
        query += " AND priority = ?"
        params.append(priority)

    query += " ORDER BY created_at DESC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    return [TicketResponse(**row_to_dict(r)) for r in rows]


def update_ticket(ticket_id: str, data: TicketUpdate) -> TicketResponse | None:
    existing = get_ticket(ticket_id)
    if existing is None:
        return None

    updates: dict = data.model_dump(exclude_unset=True)
    if not updates:
        return existing

    updates["updated_at"] = _now()

    # Serialize nested types
    if "tags" in updates:
        updates["tags"] = json.dumps(updates["tags"])
    if "metadata" in updates:
        meta = updates["metadata"]
        updates["metadata"] = json.dumps(meta) if meta else None
    if "customer_email" in updates:
        updates["customer_email"] = str(updates["customer_email"])
    for enum_field in ("category", "priority", "status"):
        if enum_field in updates and updates[enum_field] is not None:
            val = updates[enum_field]
            updates[enum_field] = val.value if hasattr(val, "value") else val

    # Handle status transition to resolved
    if updates.get("status") == Status.resolved and existing.resolved_at is None:
        updates["resolved_at"] = updates["updated_at"]

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [ticket_id]

    with get_conn() as conn:
        conn.execute(
            f"UPDATE tickets SET {set_clause} WHERE id = ?",  # noqa: S608
            values,
        )

    return get_ticket(ticket_id)


def delete_ticket(ticket_id: str) -> bool:
    with get_conn() as conn:
        result = conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    return result.rowcount > 0


def apply_classification(ticket_id: str, result: ClassificationResult) -> TicketResponse | None:
    """Apply auto-classification results to a ticket and return the updated ticket."""
    with get_conn() as conn:
        rowcount = conn.execute(
            """
            UPDATE tickets
            SET category = ?, priority = ?, classification_confidence = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                result.category.value,
                result.priority.value,
                result.confidence,
                _now(),
                ticket_id,
            ),
        ).rowcount

    if rowcount == 0:
        return None
    return get_ticket(ticket_id)
