"""Unit tests for pipeline/fraud_detector.py.

Covers the additive risk-score formula (amount tier, off-hours, cross-border,
wire-transfer bonus), the LOW/MEDIUM/HIGH boundaries at 30/60, the 100-point
cap, and the fact that this stage never rejects — it always forwards to
shared/output/ for the compliance checker.
"""
from __future__ import annotations

import json

from pipeline import fraud_detector
from tests.conftest import make_envelope, make_transaction


def _run(data):
    return fraud_detector.process_transaction(make_envelope(data, source_stage="validator", target_stage="fraud_detector"))


def _audit_lines(shared_dir):
    log_path = shared_dir / "results" / "audit_log.jsonl"
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]


def test_low_risk_domestic_transfer_scores_zero(shared_dir):
    """TXN008-equivalent: $3,200 USD domestic transfer, business hours -> score 0, LOW, passed."""
    data = make_transaction(
        transaction_id="TXN008",
        amount="3200.00",
        timestamp="2026-03-16T10:15:00Z",
        transaction_type="transfer",
        metadata={"channel": "mobile", "country": "US"},
    )
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 0
    assert envelope["data"]["risk_level"] == "LOW"
    assert envelope["data"]["fraud_status"] == "passed"
    assert envelope["target_stage"] == "compliance_checker"

    lines = _audit_lines(shared_dir)
    assert lines[0]["outcome"] == "passed:LOW"


def test_high_value_wire_transfer_scores_50_medium(shared_dir):
    """TXN002-equivalent: $25,000 USD wire transfer, business hours, domestic -> 40 (tier) + 10 (wire) = 50."""
    data = make_transaction(
        transaction_id="TXN002",
        amount="25000.00",
        timestamp="2026-03-16T09:15:00Z",
        transaction_type="wire_transfer",
        metadata={"channel": "branch", "country": "US"},
    )
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 50
    assert envelope["data"]["risk_level"] == "MEDIUM"
    assert envelope["data"]["fraud_status"] == "flagged"


def test_just_under_10k_tier_scores_15_low(shared_dir):
    """TXN003-equivalent: $9,999.99 is one cent under the $10,000 tier -> +15 only, LOW, passed."""
    data = make_transaction(
        transaction_id="TXN003",
        amount="9999.99",
        timestamp="2026-03-16T09:30:00Z",
        transaction_type="transfer",
        metadata={"channel": "online", "country": "US"},
    )
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 15
    assert envelope["data"]["risk_level"] == "LOW"
    assert envelope["data"]["fraud_status"] == "passed"


def test_off_hours_cross_border_transfer_scores_35_medium(shared_dir):
    """TXN004-equivalent: 02:47 UTC (off-hours) + DE (cross-border) + $500 (tier 0) = 35."""
    data = make_transaction(
        transaction_id="TXN004",
        amount="500.00",
        timestamp="2026-03-16T02:47:00Z",
        currency="EUR",
        transaction_type="transfer",
        metadata={"channel": "api", "country": "DE"},
    )
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 35
    assert envelope["data"]["risk_level"] == "MEDIUM"
    assert envelope["data"]["fraud_status"] == "flagged"


def test_high_value_off_hours_wire_scores_70_high(shared_dir):
    """TXN005-equivalent: $75,000 wire transfer -> 60 (tier) + 10 (wire) = 70, HIGH."""
    data = make_transaction(
        transaction_id="TXN005",
        amount="75000.00",
        timestamp="2026-03-16T10:00:00Z",
        transaction_type="wire_transfer",
        metadata={"channel": "branch", "country": "US"},
    )
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 70
    assert envelope["data"]["risk_level"] == "HIGH"
    assert envelope["data"]["fraud_status"] == "flagged"


def test_refund_amount_is_risk_scored_on_absolute_value(shared_dir):
    """TXN007-equivalent: -100.00 GBP refund, off-hours=False, cross-border (GB) -> tier 0 + 15 = 15, LOW."""
    data = make_transaction(
        transaction_id="TXN007",
        amount="-100.00",
        currency="GBP",
        timestamp="2026-03-16T10:10:00Z",
        transaction_type="refund",
        metadata={"channel": "online", "country": "GB"},
    )
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 15
    assert envelope["data"]["risk_level"] == "LOW"
    assert envelope["data"]["fraud_status"] == "passed"


def test_amount_tier_boundaries_are_strictly_greater_than(shared_dir):
    """Tiers use strict `>`, so amounts exactly at 5000/10000/50000 fall into
    the lower tier, not the higher one."""
    at_5000 = _run(make_transaction(transaction_id="T-5000", amount="5000.00"))
    assert at_5000["data"]["risk_score"] == 0

    at_10000 = _run(make_transaction(transaction_id="T-10000", amount="10000.00"))
    assert at_10000["data"]["risk_score"] == 15

    at_50000 = _run(make_transaction(transaction_id="T-50000", amount="50000.00"))
    assert at_50000["data"]["risk_score"] == 40

    just_over_50000 = _run(make_transaction(transaction_id="T-50001", amount="50000.01"))
    assert just_over_50000["data"]["risk_score"] == 60


def test_off_hours_boundary_hours(shared_dir):
    before_6am = _run(make_transaction(transaction_id="T-0559", amount="100.00", timestamp="2026-03-16T05:59:00Z"))
    assert before_6am["data"]["risk_score"] == 20  # off-hours only

    at_6am = _run(make_transaction(transaction_id="T-0600", amount="100.00", timestamp="2026-03-16T06:00:00Z"))
    assert at_6am["data"]["risk_score"] == 0  # not off-hours

    at_2159 = _run(make_transaction(transaction_id="T-2159", amount="100.00", timestamp="2026-03-16T21:59:00Z"))
    assert at_2159["data"]["risk_score"] == 0

    at_2200 = _run(make_transaction(transaction_id="T-2200", amount="100.00", timestamp="2026-03-16T22:00:00Z"))
    assert at_2200["data"]["risk_score"] == 20


def test_missing_country_defaults_to_cross_border(shared_dir):
    """Fail-safe: an unknown/missing metadata.country is treated as
    cross-border rather than silently passing."""
    data = make_transaction(transaction_id="T-NOCOUNTRY", amount="100.00", metadata={"channel": "online"})
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 15


def test_risk_score_is_capped_at_100(shared_dir):
    """60 (tier) + 20 (off-hours) + 15 (cross-border) + 10 (wire) = 105, capped to 100."""
    data = make_transaction(
        transaction_id="T-CAP",
        amount="99999.00",
        timestamp="2026-03-16T23:00:00Z",
        transaction_type="wire_transfer",
        metadata={"channel": "branch", "country": "DE"},
    )
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 100
    assert envelope["data"]["risk_level"] == "HIGH"


def test_risk_level_boundary_at_30_is_medium(shared_dir):
    """wire_transfer (+10) + off-hours (+20) + tier 0 = exactly 30 -> MEDIUM (inclusive lower bound)."""
    data = make_transaction(
        transaction_id="T-30",
        amount="100.00",
        timestamp="2026-03-16T23:00:00Z",
        transaction_type="wire_transfer",
        metadata={"channel": "branch", "country": "US"},
    )
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 30
    assert envelope["data"]["risk_level"] == "MEDIUM"
    assert envelope["data"]["fraud_status"] == "flagged"


def test_risk_level_boundary_at_60_is_high(shared_dir):
    """tier 15 (>5000) + off-hours (+20) + cross-border (+15) + wire (+10) = exactly 60 -> HIGH (inclusive lower bound)."""
    data = make_transaction(
        transaction_id="T-60",
        amount="6000.00",
        timestamp="2026-03-16T23:00:00Z",
        transaction_type="wire_transfer",
        metadata={"channel": "branch", "country": "DE"},
    )
    envelope = _run(data)

    assert envelope["data"]["risk_score"] == 60
    assert envelope["data"]["risk_level"] == "HIGH"
    assert envelope["data"]["fraud_status"] == "flagged"


def test_fraud_detector_never_rejects_and_always_forwards(shared_dir):
    """Even a score-0 record is forwarded to shared/output/ for compliance
    checking — fraud detection never terminates a record on its own."""
    data = make_transaction(transaction_id="T-FORWARD", amount="10.00")
    envelope = _run(data)

    assert envelope["data"].get("reason_code") is None
    assert envelope["target_stage"] == "compliance_checker"
    output_file = shared_dir / "output" / "T-FORWARD.json"
    assert output_file.exists()
    assert not (shared_dir / "results" / "T-FORWARD.json").exists()


def test_audit_log_has_no_pii(shared_dir):
    data = make_transaction(transaction_id="T-PII2")
    _run(data)

    lines = _audit_lines(shared_dir)
    entry = lines[0]
    assert set(entry.keys()) == {"timestamp", "stage", "transaction_id", "outcome"}
    assert entry["stage"] == "fraud_detector"
