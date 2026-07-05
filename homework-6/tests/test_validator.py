"""Unit tests for pipeline/validator.py.

Covers the happy path (VALIDATED), every rejection reason code the stage
introduces (MISSING_REQUIRED_FIELD, INVALID_AMOUNT_FORMAT,
NON_POSITIVE_AMOUNT, REFUND_MUST_BE_NEGATIVE, CURRENCY_NOT_ISO4217), the
refund sign-convention boundary, and the file-based protocol side effects
(shared/output/ vs shared/results/ writes, audit_log.jsonl content, no PII
in the audit log).
"""
from __future__ import annotations

import json

import pytest

from pipeline import validator
from tests.conftest import make_envelope, make_transaction


def _audit_lines(shared_dir):
    log_path = shared_dir / "results" / "audit_log.jsonl"
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]


def test_valid_transaction_is_validated_and_forwarded(shared_dir):
    data = make_transaction(transaction_id="TXN-VALID")
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["status"] == "VALIDATED"
    assert envelope["source_stage"] == "validator"
    assert envelope["target_stage"] == "fraud_detector"
    assert envelope["data"]["amount"] == "1500.00"
    assert envelope["data"]["currency"] == "USD"

    output_file = shared_dir / "output" / "TXN-VALID.json"
    assert output_file.exists()
    on_disk = json.loads(output_file.read_text())
    assert on_disk["data"]["status"] == "VALIDATED"

    results_file = shared_dir / "results" / "TXN-VALID.json"
    assert not results_file.exists()

    lines = _audit_lines(shared_dir)
    assert len(lines) == 1
    assert lines[0]["stage"] == "validator"
    assert lines[0]["transaction_id"] == "TXN-VALID"
    assert lines[0]["outcome"] == "VALIDATED"
    assert set(lines[0].keys()) == {"timestamp", "stage", "transaction_id", "outcome"}


def test_missing_required_field_is_rejected(shared_dir):
    data = make_transaction(transaction_id="TXN-MISSING")
    del data["destination_account"]
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["status"] == "REJECTED"
    assert envelope["data"]["reason_code"] == "MISSING_REQUIRED_FIELD"

    results_file = shared_dir / "results" / "TXN-MISSING.json"
    assert results_file.exists()
    assert not (shared_dir / "output" / "TXN-MISSING.json").exists()

    lines = _audit_lines(shared_dir)
    assert lines[0]["outcome"] == "REJECTED:MISSING_REQUIRED_FIELD"


def test_missing_metadata_dict_is_rejected(shared_dir):
    data = make_transaction(transaction_id="TXN-BADMETA", metadata="not-a-dict")
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["reason_code"] == "MISSING_REQUIRED_FIELD"


def test_unparsable_amount_is_rejected(shared_dir):
    data = make_transaction(transaction_id="TXN-BADAMOUNT", amount="not-a-number")
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["status"] == "REJECTED"
    assert envelope["data"]["reason_code"] == "INVALID_AMOUNT_FORMAT"
    lines = _audit_lines(shared_dir)
    assert lines[0]["outcome"] == "REJECTED:INVALID_AMOUNT_FORMAT"


def test_non_positive_amount_rejected_for_transfer(shared_dir):
    data = make_transaction(transaction_id="TXN-ZERO", amount="0.00", transaction_type="transfer")
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["reason_code"] == "NON_POSITIVE_AMOUNT"


def test_negative_amount_rejected_for_wire_transfer(shared_dir):
    data = make_transaction(
        transaction_id="TXN-NEGWIRE", amount="-500.00", transaction_type="wire_transfer"
    )
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["reason_code"] == "NON_POSITIVE_AMOUNT"


def test_positive_refund_amount_is_rejected(shared_dir):
    data = make_transaction(
        transaction_id="TXN-POSREFUND", amount="100.00", transaction_type="refund"
    )
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["reason_code"] == "REFUND_MUST_BE_NEGATIVE"


def test_negative_refund_amount_is_valid(shared_dir):
    """TXN007-equivalent: -100.00 GBP refund must NOT be rejected on sign alone."""
    data = make_transaction(
        transaction_id="TXN-REFUND-OK",
        amount="-100.00",
        currency="GBP",
        transaction_type="refund",
        metadata={"channel": "online", "country": "GB"},
    )
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["status"] == "VALIDATED"
    assert envelope["data"]["amount"] == "-100.00"


def test_currency_not_iso4217_is_rejected(shared_dir):
    """TXN006-equivalent: currency XYZ is rejected with CURRENCY_NOT_ISO4217."""
    data = make_transaction(transaction_id="TXN006", currency="XYZ")
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["status"] == "REJECTED"
    assert envelope["data"]["reason_code"] == "CURRENCY_NOT_ISO4217"
    lines = _audit_lines(shared_dir)
    assert lines[0]["outcome"] == "REJECTED:CURRENCY_NOT_ISO4217"


def test_currency_is_normalized_to_uppercase(shared_dir):
    data = make_transaction(transaction_id="TXN-LOWER", currency="usd")
    envelope = validator.process_transaction(make_envelope(data))

    assert envelope["data"]["status"] == "VALIDATED"
    assert envelope["data"]["currency"] == "USD"


def test_audit_log_and_result_never_contain_pii_in_the_log(shared_dir):
    """The audit log entry must only ever have exactly the four permitted
    keys — source_account/destination_account/description must never leak
    into it, even though the terminal results/ record (an internal record,
    not a log) legitimately retains them."""
    data = make_transaction(transaction_id="TXN-PII", currency="ZZZ")
    validator.process_transaction(make_envelope(data))

    lines = _audit_lines(shared_dir)
    entry = lines[0]
    assert "source_account" not in entry
    assert "destination_account" not in entry
    assert "description" not in entry

    results_file = shared_dir / "results" / "TXN-PII.json"
    on_disk = json.loads(results_file.read_text())
    # The results file is an internal record, not a log — it legitimately
    # retains the original fields.
    assert on_disk["data"]["source_account"] == "ACC-1001"


def test_dry_run_reports_valid_and_invalid_counts(tmp_path, capsys):
    """--dry-run must never write to shared/ — verified by not even setting
    PIPELINE_SHARED_DIR (no shared_dir fixture) and confirming no shared/
    directory appears as a side effect."""
    records = [
        make_transaction(transaction_id="TXN-OK"),
        make_transaction(transaction_id="TXN-BADCUR", currency="ZZZ"),
    ]
    input_path = tmp_path / "fixture.json"
    input_path.write_text(json.dumps(records), encoding="utf-8")

    validator._dry_run(str(input_path))

    out = capsys.readouterr().out
    assert "Total: 2  Valid: 1  Invalid: 1" in out
    assert "TXN-OK" in out
    assert "TXN-BADCUR" in out
    assert "CURRENCY_NOT_ISO4217" in out
    assert not (tmp_path / "shared").exists()


def test_dry_run_resolves_relative_path_against_repo_root(capsys):
    """A bare filename (no directory component) resolves against
    validator.REPO_ROOT, matching the real sample-transactions.json used by
    `/validate-transactions` and `python pipeline/validator.py --dry-run`
    with no argument."""
    validator._dry_run("sample-transactions.json")

    out = capsys.readouterr().out
    assert "Total: 8" in out
    assert "TXN006" in out
    assert "CURRENCY_NOT_ISO4217" in out


def test_main_requires_dry_run_flag(capsys):
    with pytest.raises(SystemExit) as exc_info:
        validator.main([])

    assert exc_info.value.code == 1
    assert "Usage" in capsys.readouterr().err


def test_main_dry_run_with_explicit_path(tmp_path, capsys):
    records = [make_transaction(transaction_id="TXN-MAIN")]
    input_path = tmp_path / "fixture.json"
    input_path.write_text(json.dumps(records), encoding="utf-8")

    validator.main(["--dry-run", str(input_path)])

    out = capsys.readouterr().out
    assert "Total: 1  Valid: 1  Invalid: 0" in out
