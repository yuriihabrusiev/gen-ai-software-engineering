"""Unit tests for pipeline/common.py — the shared file-based-protocol helpers
used by every stage (directory resolution honoring PIPELINE_SHARED_DIR,
envelope construction, atomic JSON writes including Decimal serialization,
the audit-trail logger, and the PII account-masking helper).
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from pipeline import common


def test_get_shared_dir_defaults_to_shared(monkeypatch):
    monkeypatch.delenv("PIPELINE_SHARED_DIR", raising=False)
    assert common.get_shared_dir() == Path("shared")


def test_get_shared_dir_honors_env_var(shared_dir):
    assert common.get_shared_dir() == shared_dir


def test_directory_helpers_point_under_shared_dir(shared_dir):
    assert common.input_dir() == shared_dir / "input"
    assert common.processing_dir() == shared_dir / "processing"
    assert common.output_dir() == shared_dir / "output"
    assert common.results_dir() == shared_dir / "results"


def test_ensure_directories_creates_all_four(shared_dir):
    common.ensure_directories()
    assert (shared_dir / "input").is_dir()
    assert (shared_dir / "processing").is_dir()
    assert (shared_dir / "output").is_dir()
    assert (shared_dir / "results").is_dir()


def test_utc_now_iso_format(shared_dir):
    timestamp = common.utc_now_iso()
    assert timestamp.endswith("Z")
    assert "T" in timestamp
    # Must be parseable as ISO 8601 once "Z" is normalized to "+00:00".
    from datetime import datetime

    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def test_new_message_id_is_unique(shared_dir):
    first = common.new_message_id()
    second = common.new_message_id()
    assert first != second
    assert len(first) == 36  # UUID4 string form


def test_make_envelope_shape(shared_dir):
    envelope = common.make_envelope(
        {"transaction_id": "T1"}, source_stage="validator", target_stage="fraud_detector"
    )
    assert set(envelope.keys()) == {
        "message_id",
        "timestamp",
        "source_stage",
        "target_stage",
        "message_type",
        "data",
    }
    assert envelope["source_stage"] == "validator"
    assert envelope["target_stage"] == "fraud_detector"
    assert envelope["message_type"] == "transaction"
    assert envelope["data"] == {"transaction_id": "T1"}


def test_make_envelope_custom_message_type(shared_dir):
    envelope = common.make_envelope({}, "a", "b", message_type="transaction_result")
    assert envelope["message_type"] == "transaction_result"


@pytest.mark.parametrize(
    "account,expected",
    [
        ("ACC-1001", "ACC-***01"),
        ("ACC-9999", "ACC-***99"),
        (None, "ACC-***"),
        ("X", "ACC-***X"),
        ("", "ACC-***"),
    ],
)
def test_mask_account(account, expected):
    assert common.mask_account(account) == expected


def test_write_json_atomic_writes_valid_json_and_no_leftover_tmp_file(shared_dir):
    target = shared_dir / "results" / "TXN-ATOMIC.json"
    common.write_json_atomic(target, {"outcome": "CLEARED"})

    assert target.exists()
    assert json.loads(target.read_text()) == {"outcome": "CLEARED"}
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_write_json_atomic_serializes_decimal_as_string(shared_dir):
    target = shared_dir / "results" / "TXN-DECIMAL.json"
    common.write_json_atomic(target, {"amount": Decimal("100.50")})

    on_disk = json.loads(target.read_text())
    assert on_disk["amount"] == "100.50"


def test_write_json_atomic_rejects_unsupported_types(shared_dir):
    target = shared_dir / "results" / "TXN-BAD.json"
    with pytest.raises(TypeError):
        common.write_json_atomic(target, {"bad": object()})


def test_write_result_writes_under_results_dir(shared_dir):
    path = common.write_result("TXN-R1", {"outcome": "CLEARED"})
    assert path == shared_dir / "results" / "TXN-R1.json"
    assert path.exists()


def test_write_to_output_uses_transaction_id_from_data(shared_dir):
    envelope = {"message_id": "m1", "data": {"transaction_id": "TXN-O1"}}
    path = common.write_to_output(envelope)
    assert path == shared_dir / "output" / "TXN-O1.json"
    assert path.exists()


def test_write_to_output_falls_back_to_message_id_when_no_transaction_id(shared_dir):
    envelope = {"message_id": "fallback-id", "data": {}}
    path = common.write_to_output(envelope)
    assert path == shared_dir / "output" / "fallback-id.json"


def test_append_audit_log_creates_directories_and_appends_lines(shared_dir):
    common.append_audit_log("validator", "TXN-A1", "VALIDATED")
    common.append_audit_log("fraud_detector", "TXN-A1", "passed:LOW")

    log_path = shared_dir / "results" / "audit_log.jsonl"
    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert len(lines) == 2
    assert lines[0] == {
        "timestamp": lines[0]["timestamp"],
        "stage": "validator",
        "transaction_id": "TXN-A1",
        "outcome": "VALIDATED",
    }
    assert lines[1]["stage"] == "fraud_detector"
    assert lines[1]["outcome"] == "passed:LOW"
    for entry in lines:
        assert set(entry.keys()) == {"timestamp", "stage", "transaction_id", "outcome"}
