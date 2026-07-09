"""Integration test — runs the full orchestrator (validator -> fraud_detector
-> compliance_checker) over fixture transaction sets via the real
shared/{input,processing,output,results}/ file-based protocol, redirected to
tmp_path. Confirms every input record produces exactly one corresponding
outcome file in shared/results/, and pins down the exact regression values
already verified for sample-transactions.json in a prior manual run.
"""
from __future__ import annotations

import json
from pathlib import Path

import orchestrator

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TRANSACTIONS_PATH = REPO_ROOT / "sample-transactions.json"


def _load_results(shared_dir, transaction_id):
    path = shared_dir / "results" / f"{transaction_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_record_in_sample_transactions_produces_a_result_file(shared_dir):
    summary = orchestrator.run_pipeline(str(SAMPLE_TRANSACTIONS_PATH))

    with SAMPLE_TRANSACTIONS_PATH.open(encoding="utf-8") as handle:
        records = json.load(handle)

    for record in records:
        result_path = shared_dir / "results" / f"{record['transaction_id']}.json"
        assert result_path.exists(), f"missing result file for {record['transaction_id']}"

    assert (shared_dir / "results" / "summary.json").exists()
    assert (shared_dir / "results" / "audit_log.jsonl").exists()
    assert summary["total"] == len(records) == 8


def test_sample_transactions_regression_values(shared_dir):
    """Pins the exact fraud-score / outcome values already verified for
    sample-transactions.json in a prior manual end-to-end run."""
    orchestrator.run_pipeline(str(SAMPLE_TRANSACTIONS_PATH))

    txn002 = _load_results(shared_dir, "TXN002")["data"]
    assert txn002["risk_score"] == 50
    assert txn002["risk_level"] == "MEDIUM"
    assert txn002["outcome"] == "HELD_FOR_REVIEW"
    assert txn002["reason_code"] == "FRAUD_RISK_FLAGGED"

    txn003 = _load_results(shared_dir, "TXN003")["data"]
    assert txn003["risk_score"] == 15
    assert txn003["risk_level"] == "LOW"
    assert txn003["outcome"] == "HELD_FOR_REVIEW"
    assert txn003["reason_code"] == "WATCHLIST_MATCH"  # held despite low fraud score

    txn004 = _load_results(shared_dir, "TXN004")["data"]
    assert txn004["risk_score"] == 35
    assert txn004["risk_level"] == "MEDIUM"
    assert txn004["outcome"] == "HELD_FOR_REVIEW"
    assert txn004["reason_code"] == "FRAUD_RISK_FLAGGED"

    txn005 = _load_results(shared_dir, "TXN005")["data"]
    assert txn005["risk_score"] == 70
    assert txn005["risk_level"] == "HIGH"
    assert txn005["outcome"] == "HELD_FOR_REVIEW"
    assert txn005["reason_code"] == "FRAUD_RISK_FLAGGED"

    txn006 = _load_results(shared_dir, "TXN006")["data"]
    assert txn006["status"] == "REJECTED"
    assert txn006["outcome"] == "REJECTED"
    assert txn006["reason_code"] == "CURRENCY_NOT_ISO4217"

    txn007 = _load_results(shared_dir, "TXN007")["data"]
    assert txn007["outcome"] == "CLEARED"  # refund sign convention passed validation

    txn008 = _load_results(shared_dir, "TXN008")["data"]
    assert txn008["risk_score"] == 0
    assert txn008["risk_level"] == "LOW"
    assert txn008["outcome"] == "CLEARED"

    summary = json.loads((shared_dir / "results" / "summary.json").read_text())
    assert summary["outcome_counts"] == {"CLEARED": 3, "HELD_FOR_REVIEW": 4, "REJECTED": 1}
    assert summary["reason_code_counts"] == {
        "FRAUD_RISK_FLAGGED": 3,
        "WATCHLIST_MATCH": 1,
        "CURRENCY_NOT_ISO4217": 1,
    }


def test_run_pipeline_returns_the_same_summary_it_writes(shared_dir):
    summary = orchestrator.run_pipeline(str(SAMPLE_TRANSACTIONS_PATH))
    on_disk = json.loads((shared_dir / "results" / "summary.json").read_text())
    assert summary == on_disk


def test_audit_log_has_one_entry_per_stage_per_surviving_record(shared_dir):
    orchestrator.run_pipeline(str(SAMPLE_TRANSACTIONS_PATH))

    log_path = shared_dir / "results" / "audit_log.jsonl"
    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    for entry in lines:
        assert set(entry.keys()) == {"timestamp", "stage", "transaction_id", "outcome"}

    # TXN006 is rejected by the validator only -> one audit entry.
    txn006_entries = [line for line in lines if line["transaction_id"] == "TXN006"]
    assert len(txn006_entries) == 1
    assert txn006_entries[0]["stage"] == "validator"

    # TXN008 survives all three stages -> one audit entry per stage.
    txn008_entries = [line for line in lines if line["transaction_id"] == "TXN008"]
    stages = [entry["stage"] for entry in txn008_entries]
    assert stages == ["validator", "fraud_detector", "compliance_checker"]


def test_small_fixture_every_record_produces_a_result_file_including_isolated_failure(
    shared_dir, tmp_path
):
    """A small, hand-built fixture set covering CLEARED, HELD_FOR_REVIEW
    (watchlist), REJECTED (validation), and a downstream exception that must
    be isolated as REJECTED/INTERNAL_ERROR without halting the rest of the
    batch (a malformed but present `timestamp` passes field-presence
    validation but is unparsable by the fraud detector's off-hours check)."""
    fixture = [
        {
            "transaction_id": "FX-CLEARED",
            "timestamp": "2026-03-16T09:00:00Z",
            "source_account": "ACC-1001",
            "destination_account": "ACC-2001",
            "amount": "100.00",
            "currency": "USD",
            "transaction_type": "transfer",
            "description": "ok",
            "metadata": {"channel": "online", "country": "US"},
        },
        {
            "transaction_id": "FX-WATCHLIST",
            "timestamp": "2026-03-16T09:00:00Z",
            "source_account": "ACC-1002",
            "destination_account": "ACC-9999",
            "amount": "100.00",
            "currency": "USD",
            "transaction_type": "transfer",
            "description": "watchlisted destination",
            "metadata": {"channel": "online", "country": "US"},
        },
        {
            "transaction_id": "FX-BADCURRENCY",
            "timestamp": "2026-03-16T09:00:00Z",
            "source_account": "ACC-1003",
            "destination_account": "ACC-2003",
            "amount": "100.00",
            "currency": "ZZZ",
            "transaction_type": "transfer",
            "description": "bad currency",
            "metadata": {"channel": "online", "country": "US"},
        },
        {
            "transaction_id": "FX-BADTIMESTAMP",
            "timestamp": "not-a-real-timestamp",
            "source_account": "ACC-1004",
            "destination_account": "ACC-2004",
            "amount": "100.00",
            "currency": "USD",
            "transaction_type": "transfer",
            "description": "malformed timestamp reaches fraud detector",
            "metadata": {"channel": "online", "country": "US"},
        },
    ]
    fixture_path = tmp_path / "fixture-transactions.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    summary = orchestrator.run_pipeline(str(fixture_path))

    assert summary["total"] == 4
    for record in fixture:
        result_path = shared_dir / "results" / f"{record['transaction_id']}.json"
        assert result_path.exists(), f"missing result file for {record['transaction_id']}"

    cleared = _load_results(shared_dir, "FX-CLEARED")["data"]
    assert cleared["outcome"] == "CLEARED"

    watchlisted = _load_results(shared_dir, "FX-WATCHLIST")["data"]
    assert watchlisted["outcome"] == "HELD_FOR_REVIEW"
    assert watchlisted["reason_code"] == "WATCHLIST_MATCH"

    bad_currency = _load_results(shared_dir, "FX-BADCURRENCY")["data"]
    assert bad_currency["outcome"] == "REJECTED"
    assert bad_currency["reason_code"] == "CURRENCY_NOT_ISO4217"

    # A record that passes field-presence validation but blows up downstream
    # (fraud detector cannot parse the timestamp) must be isolated as a
    # per-record REJECTED/INTERNAL_ERROR, not crash the batch.
    bad_timestamp = _load_results(shared_dir, "FX-BADTIMESTAMP")["data"]
    assert bad_timestamp["outcome"] == "REJECTED"
    assert bad_timestamp["reason_code"] == "INTERNAL_ERROR"

    assert summary["outcome_counts"] == {"CLEARED": 1, "HELD_FOR_REVIEW": 1, "REJECTED": 2}
