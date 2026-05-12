from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

ACCOUNT_PATTERN = r"^ACC-[A-Za-z0-9]{5}$"
SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "UAH", "PLN"}


class TransactionType(StrEnum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"


class TransactionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


Amount = Annotated[
    Decimal,
    Field(gt=0, decimal_places=2, examples=["100.50"]),
]


class TransactionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    from_account: str = Field(alias="fromAccount", pattern=ACCOUNT_PATTERN)
    to_account: str = Field(alias="toAccount", pattern=ACCOUNT_PATTERN)
    amount: Amount
    currency: str = Field(min_length=3, max_length=3)
    type: TransactionType

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        currency = value.upper()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError("Invalid currency code")
        return currency


class Transaction(TransactionCreate):
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: TransactionStatus = TransactionStatus.COMPLETED


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    error: str
    details: list[ErrorDetail]


class BalanceResponse(BaseModel):
    account_id: str = Field(alias="accountId")
    balance: Decimal
    currency: str


class SummaryResponse(BaseModel):
    account_id: str = Field(alias="accountId")
    total_deposits: Decimal = Field(alias="totalDeposits")
    total_withdrawals: Decimal = Field(alias="totalWithdrawals")
    transaction_count: int = Field(alias="transactionCount")
    most_recent_transaction_date: datetime | None = Field(alias="mostRecentTransactionDate")
