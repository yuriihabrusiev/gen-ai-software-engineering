"""Shared pytest fixtures for the transaction pipeline test suite.

Test isolation: every path helper in pipeline/common.py (and mcp/server.py)
re-reads the PIPELINE_SHARED_DIR environment variable on every call rather
than caching it at import time, so `shared_dir` below redirects all
file-based-protocol I/O to a pytest `tmp_path` for the duration of a single
test. No test in this suite may read or write the real shared/ directory at
the repo root.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def shared_dir(tmp_path, monkeypatch):
    """Point PIPELINE_SHARED_DIR at a fresh temp directory for this test only."""
    monkeypatch.setenv("PIPELINE_SHARED_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def mcp_server_module(shared_dir):
    """Load mcp/server.py as an isolated module, bypassing the ambiguity
    between the local mcp/ directory and the installed `mcp` (Model Context
    Protocol SDK) package of the same name — `import mcp.server` would
    resolve to the third-party SDK's own `mcp.server` subpackage, not our
    local file, so we load the file directly by path instead.

    Depends on `shared_dir` so PIPELINE_SHARED_DIR is already set before the
    module-level constants (none are cached at import time) are used, and a
    fresh module object is loaded per test for full independence.
    """
    module_name = "pipeline_mcp_server_under_test"
    path = REPO_ROOT / "mcp" / "server.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, f"could not load spec for {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(module_name, None)


def make_transaction(**overrides: Any) -> dict[str, Any]:
    """Build a raw transaction record (as found in sample-transactions.json)
    with sensible valid defaults, overridable per-field for test scenarios."""
    record = {
        "transaction_id": "TXN-TEST-001",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_account": "ACC-1001",
        "destination_account": "ACC-2001",
        "amount": "1500.00",
        "currency": "USD",
        "transaction_type": "transfer",
        "description": "Test transaction",
        "metadata": {"channel": "online", "country": "US"},
    }
    record.update(overrides)
    return record


def make_envelope(
    data: dict[str, Any],
    source_stage: str = "orchestrator",
    target_stage: str = "validator",
) -> dict[str, Any]:
    """Build a standard message envelope wrapping `data`, matching the shape
    every pipeline stage's process_transaction(record) expects as input."""
    return {
        "message_id": "11111111-1111-1111-1111-111111111111",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_stage": source_stage,
        "target_stage": target_stage,
        "message_type": "transaction",
        "data": data,
    }
