"""Compliance Check stage — pipeline/compliance_checker.py

Terminal stage for every transaction that survived Validation. Screens
`source_account`/`destination_account` against a static watchlist (overrides
the fraud score), then holds any fraud-flagged transaction for review, and
clears everything else. Always writes exactly one terminal record to
shared/results/<transaction_id>.json. See specification.md section 5 ("Task:
Compliance Check Stage") for the exact decision rule.

Never logs source_account, destination_account, or description in plaintext;
masks any account referenced in a human-facing message as
ACC-***<last 2 digits>.
"""
from __future__ import annotations

from typing import Any

from pipeline import common

STAGE_NAME = "compliance_checker"

# Static sanctioned/high-risk account list used for deterministic testing
# against the sample data (specification.md's "Watchlist" implementation
# note). A fictitious identifier, not a real sanctioned-entity list.
WATCHLIST_ACCOUNTS = {"ACC-9999"}


def _watchlist_hit(source_account: Any, destination_account: Any) -> Any | None:
    if source_account in WATCHLIST_ACCOUNTS:
        return source_account
    if destination_account in WATCHLIST_ACCOUNTS:
        return destination_account
    return None


def process_transaction(record: dict[str, Any]) -> dict[str, Any]:
    """Screen one fraud-scored transaction envelope and render the final outcome.

    `record` is the standard message envelope produced by the fraud
    detector. Writes the terminal record to shared/results/<transaction_id>.json
    and returns it. Sets outcome to one of CLEARED / HELD_FOR_REVIEW, with
    reason_code WATCHLIST_MATCH or FRAUD_RISK_FLAGGED when held.
    """
    common.ensure_directories()
    data = dict(record.get("data", {}))
    transaction_id = data.get("transaction_id") or "UNKNOWN"

    source_account = data.get("source_account")
    destination_account = data.get("destination_account")
    hit_account = _watchlist_hit(source_account, destination_account)

    review_note = None
    if hit_account is not None:
        outcome = "HELD_FOR_REVIEW"
        reason_code = "WATCHLIST_MATCH"
        review_note = f"Watchlist match on {common.mask_account(hit_account)}"
    elif data.get("fraud_status") == "flagged":
        outcome = "HELD_FOR_REVIEW"
        reason_code = "FRAUD_RISK_FLAGGED"
        review_note = f"Fraud risk flagged at {data.get('risk_level')} risk level"
    else:
        outcome = "CLEARED"
        reason_code = None

    final_data = {
        **data,
        "status": outcome,
        "outcome": outcome,
        "reason_code": reason_code,
        "review_note": review_note,
    }
    envelope = common.make_envelope(
        final_data, source_stage=STAGE_NAME, target_stage="results", message_type="transaction_result"
    )
    common.write_result(transaction_id, envelope)

    audit_outcome = outcome if reason_code is None else f"{outcome}:{reason_code}"
    common.append_audit_log(STAGE_NAME, transaction_id, audit_outcome)
    return envelope
