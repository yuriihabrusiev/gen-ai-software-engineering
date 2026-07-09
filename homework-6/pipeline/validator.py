"""Validation stage — pipeline/validator.py

Confirms every required field is present, parses `amount` as `decimal.Decimal`
(never `float`), enforces the sign convention for `transaction_type`, and
validates `currency` against a fixed, offline ISO 4217 allow-list. See
specification.md section 5 ("Task: Validation Stage") for the exact contract.

On failure: writes a REJECTED terminal record straight to shared/results/ and
appends an audit_log.jsonl entry with outcome 'REJECTED:<reason_code>' — the
record never reaches Fraud Detection.

On success: sets status=VALIDATED, writes the message envelope to
shared/output/ for the fraud detector, and appends an audit_log.jsonl entry
with outcome 'VALIDATED'.

Never logs source_account, destination_account, or description in plaintext.

Also runnable directly as `python pipeline/validator.py --dry-run
[path/to/transactions.json]` (see .claude/commands/validate-transactions.md)
to validate every record in a file and print a report, writing nothing to
shared/. The dry-run path (`_validate`) is a pure function shared with
`process_transaction` below, so the two can never disagree on a verdict.
`pipeline.common` is imported lazily inside the functions that need it
(`_reject`/`process_transaction`) rather than at module level, specifically
so that direct script execution — which puts only this file's own directory
on sys.path, not the repo root — can still run the dry-run path without
needing the `pipeline` package to be importable.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

STAGE_NAME = "validator"

REQUIRED_FIELDS = (
    "transaction_id",
    "timestamp",
    "source_account",
    "destination_account",
    "amount",
    "currency",
    "transaction_type",
    "description",
    "metadata",
)

# Fixed, offline ISO 4217 alphabetic currency code allow-list — deliberately a
# local constant with no network calls (see specification.md's "Currency
# validation" implementation note; context7 was consulted for `pycountry` as
# a vetted source of the full list, but the runtime check itself must stay
# local/offline and deterministic).
ISO_4217_CURRENCIES: set[str] = {
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY", "HKD",
    "SGD", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "MXN", "BRL", "ZAR",
    "INR", "KRW", "TRY", "RUB", "AED", "SAR", "ILS", "THB", "MYR", "IDR",
    "PHP", "VND", "TWD", "PKR", "EGP", "NGN", "KES", "ARS", "CLP", "COP",
}

# transaction_type -> required amount sign, per specification.md section 3
# ("Sign convention (refunds)"): transfer/wire_transfer must be strictly
# positive; refund must be strictly negative. Fraud scoring downstream always
# uses abs(amount), so a refund's magnitude is still risk-scored.
POSITIVE_AMOUNT_TYPES = {"transfer", "wire_transfer"}
NEGATIVE_AMOUNT_TYPES = {"refund"}


def _missing_required_fields(data: dict[str, Any]) -> list[str]:
    missing = [field for field in REQUIRED_FIELDS if field not in data or data[field] is None]
    if "metadata" not in missing and not isinstance(data.get("metadata"), dict):
        missing.append("metadata")
    return missing


def _validate(data: dict[str, Any]) -> tuple[str, str | None, Decimal | None, str | None]:
    """Pure validation decision for one record's `data` payload — no file
    I/O, no envelope, no side effects. Returns
    `(status, reason_code, amount, currency)`:
    - `status` is `"VALIDATED"` or `"REJECTED"`.
    - `reason_code` is one of the five rejection codes, or `None` if valid.
    - `amount`/`currency` are the parsed/normalized values once known (both
      `None` if rejected before `amount` could even be parsed).

    Shared by `process_transaction` (real pipeline) and `_dry_run` (CLI) so
    the two can never disagree on a verdict.
    """
    missing = _missing_required_fields(data)
    if missing:
        return "REJECTED", "MISSING_REQUIRED_FIELD", None, None

    try:
        amount = Decimal(str(data["amount"]))
    except (InvalidOperation, ValueError, TypeError):
        return "REJECTED", "INVALID_AMOUNT_FORMAT", None, None

    transaction_type = data.get("transaction_type")
    if transaction_type in POSITIVE_AMOUNT_TYPES and not amount > 0:
        return "REJECTED", "NON_POSITIVE_AMOUNT", amount, None
    if transaction_type in NEGATIVE_AMOUNT_TYPES and not amount < 0:
        return "REJECTED", "REFUND_MUST_BE_NEGATIVE", amount, None

    currency = str(data.get("currency", "")).upper()
    if currency not in ISO_4217_CURRENCIES:
        return "REJECTED", "CURRENCY_NOT_ISO4217", amount, currency

    return "VALIDATED", None, amount, currency


def _reject(data: dict[str, Any], transaction_id: str, reason_code: str) -> dict[str, Any]:
    from pipeline import common

    rejected_data = {
        **data,
        "status": "REJECTED",
        "outcome": "REJECTED",
        "reason_code": reason_code,
    }
    envelope = common.make_envelope(
        rejected_data,
        source_stage=STAGE_NAME,
        target_stage="results",
        message_type="transaction_result",
    )
    common.write_result(transaction_id, envelope)
    common.append_audit_log(STAGE_NAME, transaction_id, f"REJECTED:{reason_code}")
    return envelope


def process_transaction(record: dict[str, Any]) -> dict[str, Any]:
    """Validate one transaction envelope.

    `record` is the standard message envelope (message_id, timestamp,
    source_stage, target_stage, message_type, data). Returns the resulting
    envelope: a REJECTED terminal record (also written to shared/results/),
    or a VALIDATED record (also written to shared/output/ for the fraud
    detector). Never logs source_account, destination_account, or
    description in plaintext.
    """
    from pipeline import common

    common.ensure_directories()
    data = dict(record.get("data", {}))
    transaction_id = data.get("transaction_id") or "UNKNOWN"

    status, reason_code, amount, currency = _validate(data)

    if status == "REJECTED":
        assert reason_code is not None
        return _reject(data, transaction_id, reason_code)

    validated_data = {
        **data,
        "amount": str(amount),
        "currency": currency,
        "status": "VALIDATED",
    }
    envelope = common.make_envelope(
        validated_data, source_stage=STAGE_NAME, target_stage="fraud_detector"
    )
    common.write_to_output(envelope)
    common.append_audit_log(STAGE_NAME, transaction_id, "VALIDATED")
    return envelope


def _dry_run(input_path: str) -> None:
    """CLI dry-run: validate every record in `input_path` and print a
    report. Never touches shared/ — calls only the pure `_validate`, never
    `process_transaction`."""
    path = Path(input_path)
    if not path.is_absolute():
        path = REPO_ROOT / input_path
    with path.open("r", encoding="utf-8") as handle:
        records = json.load(handle)

    rows: list[tuple[str, str, str]] = []
    for record in records:
        data = dict(record)
        transaction_id = data.get("transaction_id") or "UNKNOWN"
        status, reason_code, _, _ = _validate(data)
        rows.append((transaction_id, status, reason_code or ""))

    valid = sum(1 for _, status, _ in rows if status == "VALIDATED")
    invalid = len(rows) - valid

    print(f"Total: {len(rows)}  Valid: {valid}  Invalid: {invalid}")
    print(f"{'transaction_id':<20} {'status':<10} reason")
    for transaction_id, status, reason in rows:
        print(f"{transaction_id:<20} {status:<10} {reason}")


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if "--dry-run" not in args:
        print(
            "Usage: python pipeline/validator.py --dry-run [path/to/transactions.json]",
            file=sys.stderr,
        )
        sys.exit(1)
    paths = [arg for arg in args if arg != "--dry-run"]
    input_path = paths[0] if paths else "sample-transactions.json"
    _dry_run(input_path)


if __name__ == "__main__":
    main()
