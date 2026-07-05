"""Unit tests for pipeline/compliance_checker.py.

Covers CLEARED (happy path), HELD_FOR_REVIEW via WATCHLIST_MATCH (which
overrides the fraud score), HELD_FOR_REVIEW via FRAUD_RISK_FLAGGED, the
watchlist-precedence boundary (both conditions true at once), and the
terminal-record / audit-trail side effects.
"""
from __future__ import annotations

import json

from pipeline import compliance_checker
from tests.conftest import make_envelope, make_transaction


def _scored(data, risk_score=0, risk_level="LOW", fraud_status="passed"):
    data = {**data, "risk_score": risk_score, "risk_level": risk_level, "fraud_status": fraud_status}
    return data


def _run(data):
    return compliance_checker.process_transaction(
        make_envelope(data, source_stage="fraud_detector", target_stage="compliance_checker")
    )


def _audit_lines(shared_dir):
    log_path = shared_dir / "results" / "audit_log.jsonl"
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]


def test_clean_transaction_is_cleared(shared_dir):
    """TXN008-equivalent: not watchlisted, fraud_status passed -> CLEARED."""
    data = _scored(make_transaction(transaction_id="TXN008"), risk_score=0, risk_level="LOW", fraud_status="passed")
    envelope = _run(data)

    assert envelope["data"]["outcome"] == "CLEARED"
    assert envelope["data"]["reason_code"] is None
    assert envelope["source_stage"] == "compliance_checker"
    assert envelope["target_stage"] == "results"

    results_file = shared_dir / "results" / "TXN008.json"
    assert results_file.exists()
    on_disk = json.loads(results_file.read_text())
    assert on_disk["data"]["outcome"] == "CLEARED"

    lines = _audit_lines(shared_dir)
    assert lines[0]["outcome"] == "CLEARED"


def test_watchlisted_destination_is_held_regardless_of_low_fraud_score(shared_dir):
    """TXN003-equivalent: fraud score is LOW/passed, but destination_account
    ACC-9999 is watchlisted -> HELD_FOR_REVIEW/WATCHLIST_MATCH anyway."""
    data = _scored(
        make_transaction(transaction_id="TXN003", destination_account="ACC-9999"),
        risk_score=15,
        risk_level="LOW",
        fraud_status="passed",
    )
    envelope = _run(data)

    assert envelope["data"]["outcome"] == "HELD_FOR_REVIEW"
    assert envelope["data"]["reason_code"] == "WATCHLIST_MATCH"
    assert "ACC-***99" in envelope["data"]["review_note"]

    lines = _audit_lines(shared_dir)
    assert lines[0]["outcome"] == "HELD_FOR_REVIEW:WATCHLIST_MATCH"


def test_watchlisted_source_account_is_held(shared_dir):
    data = _scored(
        make_transaction(transaction_id="TXN-SRC-WL", source_account="ACC-9999"),
        risk_score=0,
        risk_level="LOW",
        fraud_status="passed",
    )
    envelope = _run(data)

    assert envelope["data"]["outcome"] == "HELD_FOR_REVIEW"
    assert envelope["data"]["reason_code"] == "WATCHLIST_MATCH"


def test_fraud_flagged_transaction_is_held(shared_dir):
    """TXN002-equivalent: fraud_status flagged, no watchlist match -> HELD_FOR_REVIEW/FRAUD_RISK_FLAGGED."""
    data = _scored(
        make_transaction(transaction_id="TXN002"), risk_score=50, risk_level="MEDIUM", fraud_status="flagged"
    )
    envelope = _run(data)

    assert envelope["data"]["outcome"] == "HELD_FOR_REVIEW"
    assert envelope["data"]["reason_code"] == "FRAUD_RISK_FLAGGED"
    assert "MEDIUM" in envelope["data"]["review_note"]

    lines = _audit_lines(shared_dir)
    assert lines[0]["outcome"] == "HELD_FOR_REVIEW:FRAUD_RISK_FLAGGED"


def test_watchlist_takes_precedence_over_fraud_flag(shared_dir):
    """When both a watchlist hit and a fraud flag are true, WATCHLIST_MATCH wins."""
    data = _scored(
        make_transaction(transaction_id="TXN-BOTH", destination_account="ACC-9999"),
        risk_score=90,
        risk_level="HIGH",
        fraud_status="flagged",
    )
    envelope = _run(data)

    assert envelope["data"]["outcome"] == "HELD_FOR_REVIEW"
    assert envelope["data"]["reason_code"] == "WATCHLIST_MATCH"


def test_compliance_checker_writes_exactly_one_terminal_file(shared_dir):
    data = _scored(make_transaction(transaction_id="TXN-ONE"))
    _run(data)

    results_files = list((shared_dir / "results").glob("TXN-ONE*.json"))
    assert len(results_files) == 1


def test_audit_log_has_no_pii(shared_dir):
    data = _scored(make_transaction(transaction_id="TXN-PII3", destination_account="ACC-9999"))
    _run(data)

    lines = _audit_lines(shared_dir)
    entry = lines[0]
    assert set(entry.keys()) == {"timestamp", "stage", "transaction_id", "outcome"}
