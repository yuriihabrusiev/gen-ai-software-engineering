"""Fraud Detection stage — pipeline/fraud_detector.py

Consumes VALIDATED records forwarded by the validator (via shared/output/ ->
shared/processing/), computes an additive `risk_score` (0-100, capped) from
amount tier, off-hours timing, cross-border destination, and wire-transfer
channel, and always forwards the annotated record to shared/output/ for the
compliance checker. See specification.md section 5 ("Task: Fraud Detection
Stage") for the exact scoring formula and thresholds.

Fraud Detection never rejects a record on its own — it only annotates
risk_score/risk_level/fraud_status and forwards. Compliance Check makes the
final hold/clear decision. Never logs source_account, destination_account, or
description in plaintext.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pipeline import common

STAGE_NAME = "fraud_detector"

# Home-country set for the bank's domicile (specification.md's "Off-hours /
# cross-border definitions"). Any metadata.country not in this set is
# cross-border.
HOME_COUNTRIES = {"US"}

# Amount tiers are mutually exclusive on abs(amount) — apply the highest
# matching tier only.
AMOUNT_TIER_HIGH = Decimal("50000")
AMOUNT_TIER_MEDIUM = Decimal("10000")
AMOUNT_TIER_LOW = Decimal("5000")

AMOUNT_TIER_HIGH_SCORE = 60
AMOUNT_TIER_MEDIUM_SCORE = 40
AMOUNT_TIER_LOW_SCORE = 15

OFF_HOURS_SCORE = 20
CROSS_BORDER_SCORE = 15
WIRE_TRANSFER_SCORE = 10

RISK_SCORE_CAP = 100
MEDIUM_THRESHOLD = 30
HIGH_THRESHOLD = 60

OFF_HOURS_START_HOUR = 22  # UTC hour >= 22 is off-hours
OFF_HOURS_END_HOUR = 6  # UTC hour < 6 is off-hours


def _amount_tier_score(amount: Decimal) -> int:
    if amount > AMOUNT_TIER_HIGH:
        return AMOUNT_TIER_HIGH_SCORE
    if amount > AMOUNT_TIER_MEDIUM:
        return AMOUNT_TIER_MEDIUM_SCORE
    if amount > AMOUNT_TIER_LOW:
        return AMOUNT_TIER_LOW_SCORE
    return 0


def _is_off_hours(timestamp: str) -> bool:
    """UTC hour < 6 or >= 22 counts as off-hours. Expects ISO 8601, e.g.
    '2026-03-16T02:47:00Z'."""
    normalized = timestamp.replace("Z", "+00:00")
    hour = datetime.fromisoformat(normalized).hour
    return hour < OFF_HOURS_END_HOUR or hour >= OFF_HOURS_START_HOUR


def _is_cross_border(data: dict[str, Any]) -> bool:
    metadata = data.get("metadata")
    country = metadata.get("country") if isinstance(metadata, dict) else None
    # Fail-safe default: an unknown/missing country is treated as cross-border
    # rather than silently passing (see agents.md's Edge Case Handling
    # Directives: prefer reject/flag over a false-negative fraud pass).
    return country not in HOME_COUNTRIES


def _risk_level(score: int) -> str:
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def process_transaction(record: dict[str, Any]) -> dict[str, Any]:
    """Score one VALIDATED transaction envelope for fraud risk.

    `record` is the standard message envelope produced by the validator.
    Always forwards the enriched envelope to shared/output/ for the
    compliance checker — this stage never terminates a record on its own.
    Never logs source_account, destination_account, or description in
    plaintext.
    """
    common.ensure_directories()
    data = dict(record.get("data", {}))
    transaction_id = data.get("transaction_id") or "UNKNOWN"

    amount = Decimal(str(data["amount"]))
    score = _amount_tier_score(abs(amount))

    if _is_off_hours(data["timestamp"]):
        score += OFF_HOURS_SCORE

    if _is_cross_border(data):
        score += CROSS_BORDER_SCORE

    if data.get("transaction_type") == "wire_transfer":
        score += WIRE_TRANSFER_SCORE

    score = min(score, RISK_SCORE_CAP)
    risk_level = _risk_level(score)
    fraud_status = "passed" if risk_level == "LOW" else "flagged"

    enriched_data = {
        **data,
        "risk_score": score,
        "risk_level": risk_level,
        "fraud_status": fraud_status,
    }
    envelope = common.make_envelope(
        enriched_data, source_stage=STAGE_NAME, target_stage="compliance_checker"
    )
    common.write_to_output(envelope)

    outcome_prefix = "flagged" if fraud_status == "flagged" else "passed"
    common.append_audit_log(STAGE_NAME, transaction_id, f"{outcome_prefix}:{risk_level}")
    return envelope
