from fastapi import APIRouter, HTTPException, Query, UploadFile, status

from src.models.ticket import (
    Category,
    ClassificationResult,
    ImportSummary,
    Priority,
    Status,
    TicketCreate,
    TicketResponse,
    TicketUpdate,
)
from src.services import classification_service, import_service, ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])
MAX_IMPORT_BYTES = import_service.MAX_XML_IMPORT_BYTES

_SUPPORTED_CONTENT_TYPES = {
    "text/csv": "csv",
    "application/json": "json",
    "application/xml": "xml",
    "text/xml": "xml",
}


def _get_upload_size(file: UploadFile) -> int:
    current_position = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(current_position)
    return size


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: TicketCreate,
    auto_classify: bool = Query(False, description="Auto-classify the ticket on creation"),
) -> TicketResponse:
    ticket = ticket_service.create_ticket(data)
    if auto_classify:
        result = classification_service.classify(ticket.subject, ticket.description)
        updated = ticket_service.apply_classification(ticket.id, result)
        if updated is not None:
            ticket = updated
    return ticket


@router.get("", response_model=list[TicketResponse])
def list_tickets(
    status: Status | None = Query(None),
    category: Category | None = Query(None),
    priority: Priority | None = Query(None),
) -> list[TicketResponse]:
    return ticket_service.list_tickets(
        status=status.value if status else None,
        category=category.value if category else None,
        priority=priority.value if priority else None,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: str) -> TicketResponse:
    ticket = ticket_service.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.put("/{ticket_id}", response_model=TicketResponse)
def update_ticket(ticket_id: str, data: TicketUpdate) -> TicketResponse:
    ticket = ticket_service.update_ticket(ticket_id, data)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: str) -> None:
    deleted = ticket_service.delete_ticket(ticket_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")


@router.post("/{ticket_id}/auto-classify", response_model=ClassificationResult)
def auto_classify_ticket(ticket_id: str) -> ClassificationResult:
    ticket = ticket_service.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    result = classification_service.classify(ticket.subject, ticket.description)
    ticket_service.apply_classification(ticket_id, result)
    return result


@router.post("/import", response_model=ImportSummary, status_code=status.HTTP_200_OK)
def import_tickets(
    file: UploadFile,
    auto_classify: bool = Query(False, description="Auto-classify imported tickets"),
) -> ImportSummary:
    content_type = (file.content_type or "").split(";")[0].strip().lower()

    # Fall back to filename extension when content-type is generic
    fmt = _SUPPORTED_CONTENT_TYPES.get(content_type)
    if fmt is None and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        fmt = ext if ext in ("csv", "json", "xml") else None

    if fmt is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{content_type}'. Use CSV, JSON, or XML.",
        )

    if _get_upload_size(file) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Uploaded file is too large. Maximum allowed size is {MAX_IMPORT_BYTES} bytes.",
        )

    raw = file.file.read()

    try:
        if fmt == "csv":
            tickets, errors = import_service.parse_csv(raw)
        elif fmt == "json":
            tickets, errors = import_service.parse_json(raw)
        else:
            tickets, errors = import_service.parse_xml(raw)
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be valid UTF-8.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    for ticket_data in tickets:
        ticket = ticket_service.create_ticket(ticket_data)
        if auto_classify:
            result = classification_service.classify(ticket.subject, ticket.description)
            ticket_service.apply_classification(ticket.id, result)

    return import_service.build_summary(tickets, errors)
