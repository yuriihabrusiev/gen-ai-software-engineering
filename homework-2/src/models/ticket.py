from datetime import datetime
from enum import StrEnum
from typing import cast

from pydantic import BaseModel, EmailStr, Field, model_validator


class Category(StrEnum):
    account_access = "account_access"
    technical_issue = "technical_issue"
    billing_question = "billing_question"
    feature_request = "feature_request"
    bug_report = "bug_report"
    other = "other"


class Priority(StrEnum):
    urgent = "urgent"
    high = "high"
    medium = "medium"
    low = "low"


class Status(StrEnum):
    new = "new"
    in_progress = "in_progress"
    waiting_customer = "waiting_customer"
    resolved = "resolved"
    closed = "closed"


class Source(StrEnum):
    web_form = "web_form"
    email = "email"
    api = "api"
    chat = "chat"
    phone = "phone"


class DeviceType(StrEnum):
    desktop = "desktop"
    mobile = "mobile"
    tablet = "tablet"


class TicketMetadata(BaseModel):
    source: Source = Source.api
    browser: str | None = None
    device_type: DeviceType | None = None


class TicketCreate(BaseModel):
    customer_id: str
    customer_email: EmailStr
    customer_name: str
    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    category: Category | None = None
    priority: Priority = Priority.medium
    status: Status = Status.new
    assigned_to: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: TicketMetadata | None = None


class TicketUpdate(BaseModel):
    customer_id: str | None = None
    customer_email: EmailStr | None = None
    customer_name: str | None = None
    subject: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=10, max_length=2000)
    category: Category | None = None
    priority: Priority | None = None
    status: Status | None = None
    assigned_to: str | None = None
    tags: list[str] | None = None
    metadata: TicketMetadata | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        update_data = cast("dict[str, object | None]", data)
        non_nullable_fields = {
            "customer_id",
            "customer_email",
            "customer_name",
            "subject",
            "description",
            "priority",
            "status",
            "tags",
        }
        null_fields = sorted(
            field
            for field in non_nullable_fields
            if field in update_data and update_data[field] is None
        )
        if null_fields:
            fields = ", ".join(null_fields)
            raise ValueError(f"Field(s) cannot be null: {fields}")

        return data


class TicketResponse(BaseModel):
    id: str
    customer_id: str
    customer_email: str
    customer_name: str
    subject: str
    description: str
    category: Category | None = None
    priority: Priority
    status: Status
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    assigned_to: str | None = None
    tags: list[str]
    metadata: TicketMetadata | None = None
    classification_confidence: float | None = None

    model_config = {"from_attributes": True}


class ClassificationResult(BaseModel):
    category: Category
    priority: Priority
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    keywords_found: list[str]


class ImportError(BaseModel):
    row: int
    error: str


class ImportSummary(BaseModel):
    total: int
    successful: int
    failed: int
    errors: list[ImportError]
