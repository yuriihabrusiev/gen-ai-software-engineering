# Research Notes — context7 Queries (Agent 2 / Task 2 & 4)

This file logs every context7 MCP query made while building the transaction
processing pipeline (`pipeline/`, `orchestrator.py`) and the custom MCP server
(`mcp/server.py`).

## Query 1: Python decimal module — parsing, quantize, and avoiding float drift
- Search: "decimal module Decimal class parsing from string, avoiding float, rounding and quantize with ROUND_HALF_UP"
- context7 library ID: `/python/cpython`
- Applied: Confirmed the standard-library pattern of constructing `Decimal`
  directly from the original string (`Decimal("1500.00")`, never
  `Decimal(str(float_value))` or a `float` intermediate) to avoid binary
  floating-point drift — e.g. the docs example `round(.70 * 1.05, 2)` gives
  `0.73` with floats but the exact `0.74` with `Decimal('0.70') *
  Decimal('1.05')`. This is why `pipeline/validator.py`'s `parse_amount()`
  calls `decimal.Decimal(str(raw_amount))` at the very first point the amount
  is read from the JSON payload and every downstream comparison
  (`amount > 0`, tier thresholds in `pipeline/fraud_detector.py` such as
  `abs(amount) > Decimal("50000")`) stays in `Decimal` space — no `float()`
  call appears anywhere on the money code path. Also confirmed `quantize()` /
  `ROUND_HALF_UP` exists for future rounding needs, though this pipeline's
  thresholds are all strict inequalities on unrounded `Decimal` values so no
  quantization was needed for the current scoring logic.

## Query 2: FastMCP tool and resource registration patterns
- Search: "how to define a tool with @mcp.tool and a resource with @mcp.resource including dynamic resource URIs"
- context7 library ID: `/prefecthq/fastmcp`
- Applied: Confirmed the `FastMCP(name=...)` constructor plus the
  `@mcp.tool` decorator (function name becomes the tool name, docstring
  becomes its description) and the `@mcp.resource("scheme://path")` decorator
  for a **static** resource (no `{param}` placeholder needed since
  `pipeline://summary` takes no arguments — contrast with the docs' own
  `resource://config` example, which is exactly the static, parameter-free
  shape used here). Applied directly in `mcp/server.py`:
  `@mcp.tool` for `get_transaction_status(transaction_id: str)` and
  `list_pipeline_results()`, and `@mcp.resource("pipeline://summary")` for
  the summary-as-text resource. The docs' resource-template pattern
  (`@mcp.resource("weather://{city}/current")`) confirmed how the URI-based
  dispatch mechanism works so we didn't misuse the templated form for a
  no-argument resource.
