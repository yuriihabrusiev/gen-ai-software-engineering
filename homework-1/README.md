# Banking Transactions API

> **Student Name**: [Your Name]
> **Date Submitted**: [Date]
> **AI Tools Used**: Codex

---

## Project Overview

This project implements a small REST API for banking transactions using Python 3.14,
FastAPI, and in-memory storage. It is intentionally lightweight: there is no database,
authentication, or background worker, so the API can be started and tested quickly.

## Features Implemented

- Create transactions with generated IDs, timestamps, and completed status.
- List all transactions or filter them by account, type, and date range.
- Fetch a transaction by ID.
- Calculate account balances from transaction history.
- Calculate simple interest for an account balance.
- Export transactions as CSV.
- Validate positive amounts with at most 2 decimal places.
- Validate account IDs in the `ACC-XXXXX` format.
- Validate supported currency codes.
- Return structured validation errors with HTTP 400.
- Additional features: account summary, simple interest, and CSV export endpoints.

## Project Structure

```text
homework-1/
├── src/banking_transactions_api/
│   ├── main.py       # FastAPI routes and error handling
│   ├── models.py     # Pydantic models and validation rules
│   └── store.py      # In-memory transaction storage and calculations
├── demo/
│   ├── run.sh
│   ├── sample-requests.http
│   └── sample-data.json
├── docs/screenshots/
├── mise.toml
├── pyproject.toml
└── HOWTORUN.md
```

## Architecture Decisions

The API uses FastAPI with Pydantic models because that keeps request validation close to
the data model and automatically exposes OpenAPI documentation. Transactions are stored
in a module-level list to match the homework requirement for in-memory storage.

Balance and summary values are derived from the transaction list instead of being stored
separately. This avoids synchronization issues in a small demo API.

*This project was completed as part of the AI-Assisted Development course.*
