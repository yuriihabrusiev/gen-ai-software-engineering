from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from banking_transactions_api.models import (
    ACCOUNT_PATTERN,
    BalanceResponse,
    ErrorResponse,
    SummaryResponse,
    Transaction,
    TransactionCreate,
    TransactionType,
)
from banking_transactions_api.store import (
    calculate_balance,
    create_transaction,
    get_transaction,
    list_transactions,
)

app = FastAPI(
    title="Banking Transactions API",
    version="0.1.0",
    description="A small in-memory REST API for banking transactions.",
)

AccountId = Annotated[str, Path(pattern=ACCOUNT_PATTERN, examples=["ACC-12345"])]


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = []
    for error in exc.errors():
        location = [str(part) for part in error["loc"] if part not in {"body", "query", "path"}]
        details.append(
            {
                "field": ".".join(location) if location else "request",
                "message": error["msg"],
            }
        )

    return JSONResponse(
        status_code=400,
        content={"error": "Validation failed", "details": details},
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/transactions",
    response_model=Transaction,
    status_code=201,
    responses={400: {"model": ErrorResponse}},
)
def post_transaction(payload: TransactionCreate) -> Transaction:
    return create_transaction(payload)


@app.get("/transactions", response_model=list[Transaction])
def get_transactions(
    account_id: Annotated[str | None, Query(alias="accountId", pattern=ACCOUNT_PATTERN)] = None,
    transaction_type: Annotated[TransactionType | None, Query(alias="type")] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> list[Transaction]:
    return list_transactions(
        account_id=account_id,
        transaction_type=transaction_type,
        from_date=from_date,
        to_date=to_date,
    )


@app.get("/transactions/{transaction_id}", response_model=Transaction)
def get_transaction_by_id(transaction_id: str) -> Transaction:
    transaction = get_transaction(transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@app.get("/accounts/{account_id}/balance", response_model=BalanceResponse)
def get_account_balance(account_id: AccountId) -> BalanceResponse:
    return BalanceResponse(accountId=account_id, balance=calculate_balance(account_id), currency="USD")


@app.get("/accounts/{account_id}/summary", response_model=SummaryResponse)
def get_account_summary(account_id: AccountId) -> SummaryResponse:
    account_transactions = list_transactions(account_id=account_id)
    deposits = Decimal("0")
    withdrawals = Decimal("0")

    for transaction in account_transactions:
        if transaction.type == TransactionType.DEPOSIT and transaction.to_account == account_id:
            deposits += transaction.amount
        elif transaction.type == TransactionType.WITHDRAWAL and transaction.from_account == account_id:
            withdrawals += transaction.amount
        elif transaction.type == TransactionType.TRANSFER:
            if transaction.to_account == account_id:
                deposits += transaction.amount
            if transaction.from_account == account_id:
                withdrawals += transaction.amount

    most_recent = max(
        (transaction.timestamp for transaction in account_transactions),
        default=None,
    )

    return SummaryResponse(
        accountId=account_id,
        totalDeposits=deposits,
        totalWithdrawals=withdrawals,
        transactionCount=len(account_transactions),
        mostRecentTransactionDate=most_recent,
    )
