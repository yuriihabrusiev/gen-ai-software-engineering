#!/usr/bin/env bash
set -euo pipefail

uv run fastapi dev src/banking_transactions_api/main.py
