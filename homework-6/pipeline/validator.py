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
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pipeline import common

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


def _reject(data: dict[str, Any], transaction_id: str, reason_code: str) -> dict[str, Any]:
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
    common.ensure_directories()
    data = dict(record.get("data", {}))
    transaction_id = data.get("transaction_id") or "UNKNOWN"

    missing = _missing_required_fields(data)
    if missing:
        return _reject(data, transaction_id, "MISSING_REQUIRED_FIELD")

    try:
        amount = Decimal(str(data["amount"]))
    except (InvalidOperation, ValueError, TypeError):
        return _reject(data, transaction_id, "INVALID_AMOUNT_FORMAT")

    transaction_type = data.get("transaction_type")
    if transaction_type in POSITIVE_AMOUNT_TYPES and not amount > 0:
        return _reject(data, transaction_id, "NON_POSITIVE_AMOUNT")
    if transaction_type in NEGATIVE_AMOUNT_TYPES and not amount < 0:
        return _reject(data, transaction_id, "REFUND_MUST_BE_NEGATIVE")

    currency = str(data.get("currency", "")).upper()
    if currency not in ISO_4217_CURRENCIES:
        return _reject(data, transaction_id, "CURRENCY_NOT_ISO4217")

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
