from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    priority: Priority = Priority.MEDIUM
    due_date: date | None = None


class Task(BaseModel):
    id: int
    title: str
    priority: Priority
    due_date: date | None
    completed: bool = False
