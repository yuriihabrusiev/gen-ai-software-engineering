"""Unit tests for mcp/server.py — the read-only FastMCP status server.

Covers the two tools (`get_transaction_status`, `list_pipeline_results`) and
the `pipeline://summary` resource, all against shared/results/ redirected to
a tmp_path fixture directory. The module is loaded directly from its file
path (see conftest.mcp_server_module) to avoid the ambiguity between the
local mcp/ directory and the installed third-party `mcp` (Model Context
Protocol SDK) package, which also ships its own `mcp.server` subpackage.
"""
from __future__ import annotations

import json


def _write_result(shared_dir, transaction_id, data):
    results_dir = shared_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "message_id": "m1",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_stage": "compliance_checker",
        "target_stage": "results",
        "message_type": "transaction_result",
        "data": data,
    }
    (results_dir / f"{transaction_id}.json").write_text(json.dumps(envelope), encoding="utf-8")


def _write_summary(shared_dir, summary):
    results_dir = shared_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


def _held_transaction_data(transaction_id="TXN-HELD"):
    return {
        "transaction_id": transaction_id,
        "source_account": "ACC-1001",
        "destination_account": "ACC-9999",
        "description": "secret consulting payment",
        "amount": "100.00",
        "currency": "USD",
        "status": "HELD_FOR_REVIEW",
        "outcome": "HELD_FOR_REVIEW",
        "reason_code": "WATCHLIST_MATCH",
        "risk_score": 15,
        "risk_level": "LOW",
        "fraud_status": "passed",
    }


# --- get_transaction_status ------------------------------------------------


def test_get_transaction_status_found_strips_pii(shared_dir, mcp_server_module):
    _write_result(shared_dir, "TXN-HELD", _held_transaction_data())

    result = mcp_server_module.get_transaction_status("TXN-HELD")

    assert result == {
        "found": True,
        "transaction_id": "TXN-HELD",
        "status": "HELD_FOR_REVIEW",
        "outcome": "HELD_FOR_REVIEW",
        "reason_code": "WATCHLIST_MATCH",
        "risk_score": 15,
        "risk_level": "LOW",
        "fraud_status": "passed",
    }
    assert "source_account" not in result
    assert "destination_account" not in result
    assert "description" not in result


def test_get_transaction_status_not_found(shared_dir, mcp_server_module):
    result = mcp_server_module.get_transaction_status("TXN-DOES-NOT-EXIST")
    assert result == {"found": False, "transaction_id": "TXN-DOES-NOT-EXIST"}


def test_get_transaction_status_cleared_transaction(shared_dir, mcp_server_module):
    _write_result(
        shared_dir,
        "TXN-CLEAR",
        {
            "transaction_id": "TXN-CLEAR",
            "source_account": "ACC-1",
            "destination_account": "ACC-2",
            "description": "d",
            "status": "CLEARED",
            "outcome": "CLEARED",
            "reason_code": None,
            "risk_score": 0,
            "risk_level": "LOW",
            "fraud_status": "passed",
        },
    )

    result = mcp_server_module.get_transaction_status("TXN-CLEAR")
    assert result["found"] is True
    assert result["outcome"] == "CLEARED"
    assert result["reason_code"] is None


# --- list_pipeline_results ---------------------------------------------------


def test_list_pipeline_results_empty_when_results_dir_missing(shared_dir, mcp_server_module):
    result = mcp_server_module.list_pipeline_results()
    assert result == {"total": 0, "transactions": [], "summary": None}


def test_list_pipeline_results_lists_all_transactions_and_strips_pii(shared_dir, mcp_server_module):
    _write_result(shared_dir, "TXN-A", _held_transaction_data("TXN-A"))
    _write_result(
        shared_dir,
        "TXN-B",
        {
            "transaction_id": "TXN-B",
            "source_account": "ACC-9",
            "destination_account": "ACC-8",
            "description": "d",
            "status": "CLEARED",
            "outcome": "CLEARED",
            "reason_code": None,
            "risk_score": 0,
            "risk_level": "LOW",
            "fraud_status": "passed",
        },
    )
    _write_summary(shared_dir, {"total": 2, "outcome_counts": {"HELD_FOR_REVIEW": 1, "CLEARED": 1}})

    result = mcp_server_module.list_pipeline_results()

    assert result["total"] == 2
    ids = {entry["transaction_id"] for entry in result["transactions"]}
    assert ids == {"TXN-A", "TXN-B"}
    for entry in result["transactions"]:
        assert "source_account" not in entry
        assert "destination_account" not in entry
        assert "description" not in entry
        assert set(entry.keys()) == {"transaction_id", "outcome", "reason_code", "risk_level"}

    assert result["summary"] == {"total": 2, "outcome_counts": {"HELD_FOR_REVIEW": 1, "CLEARED": 1}}


def test_list_pipeline_results_skips_summary_json_as_a_transaction(shared_dir, mcp_server_module):
    _write_result(shared_dir, "TXN-ONLY", _held_transaction_data("TXN-ONLY"))
    _write_summary(shared_dir, {"total": 1})

    result = mcp_server_module.list_pipeline_results()

    assert result["total"] == 1
    assert result["transactions"][0]["transaction_id"] == "TXN-ONLY"


def test_list_pipeline_results_with_no_summary_yet(shared_dir, mcp_server_module):
    _write_result(shared_dir, "TXN-NOSUM", _held_transaction_data("TXN-NOSUM"))

    result = mcp_server_module.list_pipeline_results()

    assert result["summary"] is None
    assert result["total"] == 1


# --- pipeline://summary resource --------------------------------------------


def test_pipeline_summary_resource_when_no_run_yet(shared_dir, mcp_server_module):
    text = mcp_server_module.pipeline_summary()
    assert text == "No pipeline run summary found yet. Run `python orchestrator.py` first."


def test_pipeline_summary_resource_returns_formatted_json(shared_dir, mcp_server_module):
    summary = {"total": 8, "outcome_counts": {"CLEARED": 3, "HELD_FOR_REVIEW": 4, "REJECTED": 1}}
    _write_summary(shared_dir, summary)

    text = mcp_server_module.pipeline_summary()

    assert json.loads(text) == summary
    assert text == json.dumps(summary, indent=2)


def test_shared_results_dir_resolves_against_pipeline_shared_dir_env(shared_dir, mcp_server_module):
    assert mcp_server_module._shared_results_dir() == shared_dir / "results"


def test_shared_results_dir_resolves_relative_path_against_repo_root(monkeypatch, mcp_server_module):
    """A relative PIPELINE_SHARED_DIR is resolved against the mcp package's
    own repo root, mirroring pipeline/common.py's default of a plain
    ./shared directory. This only inspects a computed Path — it performs no
    filesystem I/O, so it never touches the real repo's shared/ directory."""
    monkeypatch.setenv("PIPELINE_SHARED_DIR", "some_relative_shared_dir_that_does_not_exist")

    resolved = mcp_server_module._shared_results_dir()

    assert resolved == mcp_server_module.REPO_ROOT / "some_relative_shared_dir_that_does_not_exist" / "results"


def test_list_pipeline_results_skips_unreadable_result_file(shared_dir, mcp_server_module, monkeypatch):
    """A result file that disappears/becomes unreadable between the glob()
    listing and the read (e.g. a race with another process) must be skipped
    rather than crashing the tool."""
    _write_result(shared_dir, "TXN-RACE", _held_transaction_data("TXN-RACE"))

    original_read_json = mcp_server_module._read_json

    def _flaky_read_json(path):
        if path.name == "TXN-RACE.json":
            return None
        return original_read_json(path)

    monkeypatch.setattr(mcp_server_module, "_read_json", _flaky_read_json)

    result = mcp_server_module.list_pipeline_results()

    assert result == {"total": 0, "transactions": [], "summary": None}
