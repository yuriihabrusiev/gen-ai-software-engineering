"""orchestrator.py — Transaction Processing Pipeline orchestrator/runner.

Sets up the shared/{input,processing,output,results}/ directory tree, loads
`sample-transactions.json`, and drives every record through the three
pipeline stages — Validation -> Fraud Detection -> Compliance Check — using
only the file-based protocol (no stage's internals are imported or called
directly by another stage; the orchestrator only invokes each stage's public
`process_transaction`). Per-record exceptions are isolated so one bad record
can never halt the batch. After the run, writes shared/results/summary.json
(counts by outcome and by reason code) and prints a PII-free human-readable
summary to stdout.

See specification.md section 5 ("Task: Orchestrator / Runner") for the full
contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pipeline import common, compliance_checker, fraud_detector, validator

REPO_ROOT = Path(__file__).resolve().parent


def _load_records(input_path: str) -> list[dict[str, Any]]:
    path = Path(input_path)
    if not path.is_absolute():
        path = REPO_ROOT / input_path
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_internal_error(transaction_id: str, exc: Exception, stage: str) -> dict[str, Any]:
    """Isolate a per-record failure: write a REJECTED/INTERNAL_ERROR terminal
    record and log the exception type/message only — never the record
    payload, which may contain source_account/destination_account/description."""
    result_data = {
        "transaction_id": transaction_id,
        "status": "REJECTED",
        "outcome": "REJECTED",
        "reason_code": "INTERNAL_ERROR",
    }
    envelope = common.make_envelope(
        result_data, source_stage="orchestrator", target_stage="results", message_type="transaction_result"
    )
    common.write_result(transaction_id, envelope)
    common.append_audit_log("orchestrator", transaction_id, "REJECTED:INTERNAL_ERROR")
    print(
        f"[orchestrator] INTERNAL_ERROR while processing {transaction_id} at stage '{stage}': "
        f"{type(exc).__name__}: {exc}",
        file=sys.stderr,
    )
    return envelope


def _move_input_to_processing(transaction_id: str, raw_record: dict[str, Any]) -> Path:
    envelope = common.make_envelope(raw_record, source_stage="orchestrator", target_stage="validator")
    input_path = common.input_dir() / f"{transaction_id}.json"
    common.write_json_atomic(input_path, envelope)
    processing_path = common.processing_dir() / f"{transaction_id}.json"
    input_path.replace(processing_path)
    return processing_path


def _move_output_to_processing(transaction_id: str) -> Path | None:
    output_path = common.output_dir() / f"{transaction_id}.json"
    if not output_path.exists():
        return None
    processing_path = common.processing_dir() / f"{transaction_id}.json"
    output_path.replace(processing_path)
    return processing_path


def _read_envelope(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_validated(envelope: dict[str, Any]) -> bool:
    return envelope.get("data", {}).get("status") == "VALIDATED"


def _process_one(raw_record: dict[str, Any]) -> dict[str, Any]:
    """Drive a single raw record through validator -> fraud_detector ->
    compliance_checker via the shared/{input,processing,output,results}/
    file protocol. Returns the terminal envelope."""
    transaction_id = raw_record.get("transaction_id") or "UNKNOWN"
    common.ensure_directories()

    # orchestrator: input/ -> processing/
    try:
        processing_path = _move_input_to_processing(transaction_id, raw_record)
        envelope = _read_envelope(processing_path)
    except Exception as exc:
        return _write_internal_error(transaction_id, exc, "input_to_processing")
    finally:
        processing_path_var = common.processing_dir() / f"{transaction_id}.json"
        processing_path_var.unlink(missing_ok=True)

    # validator stage
    try:
        result = validator.process_transaction(envelope)
    except Exception as exc:
        return _write_internal_error(transaction_id, exc, "validator")

    if not _is_validated(result):
        return result  # validator already wrote the REJECTED terminal record

    # orchestrator: output/ -> processing/, then fraud_detector stage
    processing_path = _move_output_to_processing(transaction_id)
    if processing_path is None:
        return _write_internal_error(
            transaction_id, FileNotFoundError("expected shared/output/ file from validator"), "validator_handoff"
        )
    try:
        envelope = _read_envelope(processing_path)
        result = fraud_detector.process_transaction(envelope)
    except Exception as exc:
        return _write_internal_error(transaction_id, exc, "fraud_detector")
    finally:
        processing_path.unlink(missing_ok=True)

    # orchestrator: output/ -> processing/, then compliance_checker stage
    processing_path = _move_output_to_processing(transaction_id)
    if processing_path is None:
        return _write_internal_error(
            transaction_id,
            FileNotFoundError("expected shared/output/ file from fraud_detector"),
            "fraud_detector_handoff",
        )
    try:
        envelope = _read_envelope(processing_path)
        result = compliance_checker.process_transaction(envelope)
    except Exception as exc:
        return _write_internal_error(transaction_id, exc, "compliance_checker")
    finally:
        processing_path.unlink(missing_ok=True)

    return result


def run_pipeline(input_path: str = "sample-transactions.json") -> dict[str, Any]:
    """Run every record in `input_path` through the three-stage pipeline.

    Creates shared/{input,processing,output,results}/ if missing, drives each
    record through Validation -> Fraud Detection -> Compliance Check via the
    file-based protocol only, isolates per-record exceptions so one bad
    record never halts the batch, writes shared/results/summary.json, prints
    a PII-free human-readable summary, and returns the summary dict.
    """
    common.ensure_directories()
    records = _load_records(input_path)

    outcome_counts: dict[str, int] = {}
    reason_code_counts: dict[str, int] = {}
    transaction_ids: list[str] = []

    for raw_record in records:
        transaction_id = raw_record.get("transaction_id") or "UNKNOWN"
        try:
            result = _process_one(raw_record)
        except Exception as exc:  # last-resort safety net; _process_one already isolates stage errors
            result = _write_internal_error(transaction_id, exc, "orchestrator")

        data = result.get("data", {})
        outcome = data.get("outcome") or data.get("status") or "UNKNOWN"
        reason_code = data.get("reason_code")

        transaction_ids.append(data.get("transaction_id") or transaction_id)
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        if reason_code:
            reason_code_counts[reason_code] = reason_code_counts.get(reason_code, 0) + 1

    summary = {
        "generated_at": common.utc_now_iso(),
        "total": len(records),
        "outcome_counts": outcome_counts,
        "reason_code_counts": reason_code_counts,
        "transaction_ids": transaction_ids,
    }
    common.write_json_atomic(common.results_dir() / "summary.json", summary)

    _print_summary(summary)
    return summary


def _print_summary(summary: dict[str, Any]) -> None:
    """Human-readable stdout summary. Contains no PII — only counts and codes."""
    print("Transaction Processing Pipeline - run summary")
    print(f"  Total transactions: {summary['total']}")
    print("  Outcomes:")
    for outcome, count in sorted(summary["outcome_counts"].items()):
        print(f"    {outcome}: {count}")
    if summary["reason_code_counts"]:
        print("  Reason codes:")
        for reason, count in sorted(summary["reason_code_counts"].items()):
            print(f"    {reason}: {count}")
    print(f"  Results written to: {common.results_dir()}")


def main() -> None:
    input_path = sys.argv[1] if len(sys.argv) > 1 else "sample-transactions.json"
    run_pipeline(input_path)


if __name__ == "__main__":
    main()
