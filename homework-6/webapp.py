"""webapp.py — persistent web wrapper around the transaction pipeline, used
only for the hosted demo deployment (Render). This is not part of the graded
Task 2 deliverable: `python orchestrator.py` plus `python -m http.server` is
still the documented local workflow in HOWTORUN.md, and `frontend/` keeps
fetching the same `/shared/results/...` paths either way.

Two things a PaaS process needs that the local workflow doesn't:
  1. A long-running server (PaaS platforms run one process, not "run a batch
     script then separately serve static files").
  2. PII scrubbing on every response — specification.md's PII exemption for
     `shared/results/<id>.json` ("not a log, an internal record") assumed
     local-only filesystem access. Once that file is served over the public
     internet, source_account/destination_account/description need to be
     stripped the same way mcp/server.py already strips them for MCP clients.
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

import orchestrator
from pipeline.common import results_dir

REPO_ROOT = Path(__file__).resolve().parent

# Mirrors mcp/server.py's _PII_FIELDS — kept as a separate constant rather
# than a shared import so this demo-only file has no dependency on the
# graded mcp/ package.
_PII_FIELDS = ("source_account", "destination_account", "description")


def _read_json(path: Path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _scrub(data: dict) -> dict:
    return {key: value for key, value in data.items() if key not in _PII_FIELDS}


async def index(request):
    return RedirectResponse(url="/frontend/")


async def healthcheck(request):
    return PlainTextResponse("ok")


async def get_summary(request):
    summary = _read_json(results_dir() / "summary.json")
    if summary is None:
        return JSONResponse(
            {"total": 0, "outcome_counts": {}, "reason_code_counts": {}, "transaction_ids": []}
        )
    return JSONResponse(summary)


async def get_transaction(request):
    transaction_id = request.path_params["transaction_id"]
    record = _read_json(results_dir() / f"{transaction_id}.json")
    if record is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    scrubbed = dict(record)
    scrubbed["data"] = _scrub(record.get("data", {}))
    return JSONResponse(scrubbed)


async def run_pipeline(request):
    summary = orchestrator.run_pipeline()
    return JSONResponse(summary)


@asynccontextmanager
async def lifespan(app: Starlette):
    if not (results_dir() / "summary.json").exists():
        orchestrator.run_pipeline()
    yield


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/", index),
        Route("/healthz", healthcheck),
        Route("/api/run", run_pipeline, methods=["POST"]),
        Route("/shared/results/summary.json", get_summary),
        Route("/shared/results/{transaction_id}.json", get_transaction),
        Mount("/frontend", app=StaticFiles(directory=str(REPO_ROOT / "frontend"), html=True)),
    ],
)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
