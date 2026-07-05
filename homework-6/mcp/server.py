"""mcp/server.py — custom FastMCP server for the transaction pipeline (Task 4).

Read-only status server. Exposes:
  - Tool `get_transaction_status(transaction_id)`: current status of one
    transaction, read from shared/results/<transaction_id>.json.
  - Tool `list_pipeline_results()`: a summary of every processed transaction
    plus the latest run summary.
  - Resource `pipeline://summary`: the latest shared/results/summary.json as
    text.

This server only ever reads from shared/results/ — it never writes to or
mutates pipeline state (see agents.md's "Security & Compliance Constraints").
PII fields (source_account, destination_account, description) are stripped
from every value returned to an MCP client.

Run standalone: `python mcp/server.py` (also wired up as the "pipeline-status"
server in .mcp.json).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP(name="pipeline-status")

REPO_ROOT = Path(__file__).resolve().parent.parent

# PII fields that must never be echoed back to an MCP client in plaintext,
# per agents.md's PII rule.
_PII_FIELDS = ("source_account", "destination_account", "description")


def _shared_results_dir() -> Path:
    """Resolve shared/results/, honoring PIPELINE_SHARED_DIR like the pipeline
    stages do, so this server can point at a test fixture directory too."""
    shared_dir = Path(os.environ.get("PIPELINE_SHARED_DIR", "shared"))
    if not shared_dir.is_absolute():
        shared_dir = REPO_ROOT / shared_dir
    return shared_dir / "results"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _public_data(record: dict[str, Any]) -> dict[str, Any]:
    """Strip PII fields from a terminal record's `data` payload before
    returning it to an MCP client. Defensive against a malformed result file
    where `data` is present but not a dict (e.g. `null`)."""
    raw = record.get("data")
    data = dict(raw) if isinstance(raw, dict) else {}
    for field in _PII_FIELDS:
        data.pop(field, None)
    return data


@mcp.tool
def get_transaction_status(transaction_id: str) -> dict[str, Any]:
    """Return the current status/outcome of one transaction.

    Reads shared/results/<transaction_id>.json (read-only; never mutates
    pipeline state). If the file doesn't exist yet — the pipeline hasn't run,
    or this transaction hasn't reached a terminal stage — returns
    {"found": False, "transaction_id": transaction_id}. source_account,
    destination_account, and description are never included in the response.
    """
    result_path = _shared_results_dir() / f"{transaction_id}.json"
    record = _read_json(result_path)
    if record is None:
        return {"found": False, "transaction_id": transaction_id}

    data = _public_data(record)
    return {
        "found": True,
        "transaction_id": data.get("transaction_id", transaction_id),
        "status": data.get("status"),
        "outcome": data.get("outcome"),
        "reason_code": data.get("reason_code"),
        "risk_score": data.get("risk_score"),
        "risk_level": data.get("risk_level"),
        "fraud_status": data.get("fraud_status"),
    }


@mcp.tool
def list_pipeline_results() -> dict[str, Any]:
    """Return a summary of every processed transaction found in shared/results/.

    Reads every shared/results/<transaction_id>.json (skipping
    audit_log.jsonl and summary.json) and includes the latest
    shared/results/summary.json if present. Read-only — never writes to
    shared/. PII fields are stripped from each transaction entry.
    """
    results_dir = _shared_results_dir()
    if not results_dir.exists():
        return {"total": 0, "transactions": [], "summary": None}

    transactions = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        record = _read_json(path)
        if record is None:
            continue
        data = _public_data(record)
        transactions.append(
            {
                "transaction_id": data.get("transaction_id", path.stem),
                "outcome": data.get("outcome") or data.get("status"),
                "reason_code": data.get("reason_code"),
                "risk_level": data.get("risk_level"),
            }
        )

    summary = _read_json(results_dir / "summary.json")
    return {"total": len(transactions), "transactions": transactions, "summary": summary}


@mcp.resource("pipeline://summary")
def pipeline_summary() -> str:
    """Return the latest pipeline run summary (shared/results/summary.json) as text."""
    summary = _read_json(_shared_results_dir() / "summary.json")
    if summary is None:
        return "No pipeline run summary found yet. Run `python orchestrator.py` first."
    return json.dumps(summary, indent=2)


if __name__ == "__main__":
    mcp.run()
