"""Shared helpers for the transaction pipeline stages.

Provides: the standard message envelope, the shared/{input,processing,output,
results}/ directory helpers, atomic JSON writes, the audit-trail logger, and
a PII-masking helper. Every path helper re-reads the `PIPELINE_SHARED_DIR`
environment variable on each call (rather than caching a module-level
constant at import time) so tests can point the pipeline at a temp directory
via `monkeypatch.setenv("PIPELINE_SHARED_DIR", str(tmp_path))` without
needing to reload any module.

Nothing in this module ever writes `source_account`, `destination_account`,
or `description` to the audit log — `append_audit_log` only accepts a
`stage`, `transaction_id`, and `outcome` string, by construction.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


def get_shared_dir() -> Path:
    """Root of the file-based protocol directory tree (default: ./shared)."""
    return Path(os.environ.get("PIPELINE_SHARED_DIR", "shared"))


def input_dir() -> Path:
    return get_shared_dir() / "input"


def processing_dir() -> Path:
    return get_shared_dir() / "processing"


def output_dir() -> Path:
    return get_shared_dir() / "output"


def results_dir() -> Path:
    return get_shared_dir() / "results"


def ensure_directories() -> None:
    """Create shared/{input,processing,output,results}/ if missing."""
    for directory in (input_dir(), processing_dir(), output_dir(), results_dir()):
        directory.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    """Current time as an ISO 8601 UTC timestamp, e.g. 2026-03-16T10:00:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_message_id() -> str:
    return str(uuid.uuid4())


def make_envelope(
    data: dict[str, Any],
    source_stage: str,
    target_stage: str,
    message_type: str = "transaction",
) -> dict[str, Any]:
    """Build one standard message envelope (message_id, timestamp, source_stage,
    target_stage, message_type, data) per the file-based protocol."""
    return {
        "message_id": new_message_id(),
        "timestamp": utc_now_iso(),
        "source_stage": source_stage,
        "target_stage": target_stage,
        "message_type": message_type,
        "data": data,
    }


def mask_account(account: Any) -> str:
    """Mask an account identifier for any human-facing message: ACC-***<last 2 digits>."""
    text = "" if account is None else str(account)
    last_two = text[-2:] if len(text) >= 2 else text
    return f"ACC-***{last_two}"


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON to `path` via a temp-file-then-rename to avoid partial reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=_json_default)
    tmp_path.replace(path)


def write_result(transaction_id: str, payload: dict[str, Any]) -> Path:
    """Write a terminal record to shared/results/<transaction_id>.json."""
    path = results_dir() / f"{transaction_id}.json"
    write_json_atomic(path, payload)
    return path


def write_to_output(envelope: dict[str, Any]) -> Path:
    """Write an envelope for the next stage to shared/output/<transaction_id>.json."""
    transaction_id = envelope.get("data", {}).get("transaction_id") or envelope["message_id"]
    path = output_dir() / f"{transaction_id}.json"
    write_json_atomic(path, envelope)
    return path


def append_audit_log(stage: str, transaction_id: str, outcome: str) -> None:
    """Append one JSON Lines audit entry: {timestamp, stage, transaction_id, outcome}.

    No other fields are permitted here — this is the only function allowed to
    write to shared/results/audit_log.jsonl, and it never accepts (let alone
    writes) source_account, destination_account, or description.
    """
    ensure_directories()
    entry = {
        "timestamp": utc_now_iso(),
        "stage": stage,
        "transaction_id": transaction_id,
        "outcome": outcome,
    }
    log_path = results_dir() / "audit_log.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
