from datetime import date
from decimal import Decimal

from banking_transactions_api.models import (
    Transaction,
    TransactionCreate,
    TransactionType,
)

transactions: list[Transaction] = []


def create_transaction(payload: TransactionCreate) -> Transaction:
    transaction = Transaction.model_validate(payload.model_dump(by_alias=True))
    transactions.append(transaction)
    return transaction


def list_transactions(
    account_id: str | None = None,
    transaction_type: TransactionType | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[Transaction]:
    results = transactions

    if account_id:
        results = [
            transaction
            for transaction in results
            if transaction.from_account == account_id or transaction.to_account == account_id
        ]
    if transaction_type:
        results = [transaction for transaction in results if transaction.type == transaction_type]
    if from_date:
        results = [transaction for transaction in results if transaction.timestamp.date() >= from_date]
    if to_date:
        results = [transaction for transaction in results if transaction.timestamp.date() <= to_date]

    return results


def get_transaction(transaction_id: str) -> Transaction | None:
    return next(
        (transaction for transaction in transactions if transaction.id == transaction_id),
        None,
    )


def calculate_balance(account_id: str) -> Decimal:
    balance = Decimal("0")

    for transaction in transactions:
        if transaction.type == TransactionType.DEPOSIT and transaction.to_account == account_id:
            balance += transaction.amount
        elif transaction.type == TransactionType.WITHDRAWAL and transaction.from_account == account_id:
            balance -= transaction.amount
        elif transaction.type == TransactionType.TRANSFER:
            if transaction.from_account == account_id:
                balance -= transaction.amount
            if transaction.to_account == account_id:
                balance += transaction.amount

    return balance
