# How to Run the Application

## Prerequisites

- `mise`
- `uv`

The project is configured for Python 3.14 and the latest `uv` through `mise.toml`.

## Setup

Install the configured tools:

```bash
mise install
```

Install project dependencies:

```bash
mise run setup
```

Equivalent direct `uv` command:

```bash
uv sync
```

## Run the API

Start the FastAPI development server:

```bash
mise run dev
```

Equivalent direct command:

```bash
uv run fastapi dev src/banking_transactions_api/main.py
```

The API runs at:

```text
http://127.0.0.1:8000
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## Try Sample Requests

Create a transaction:

```bash
curl -X POST http://127.0.0.1:8000/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "fromAccount": "ACC-12345",
    "toAccount": "ACC-67890",
    "amount": 100.50,
    "currency": "USD",
    "type": "transfer"
  }'
```

List all transactions:

```bash
curl http://127.0.0.1:8000/transactions
```

Filter by account:

```bash
curl "http://127.0.0.1:8000/transactions?accountId=ACC-12345"
```

Get account balance:

```bash
curl http://127.0.0.1:8000/accounts/ACC-12345/balance
```

Get account summary:

```bash
curl http://127.0.0.1:8000/accounts/ACC-12345/summary
```

You can also use `demo/sample-requests.http` with the VS Code REST Client extension or a
compatible HTTP client.

## Quality Checks

Run linting and type checks:

```bash
mise run test
```

Or run each check directly:

```bash
uv run ruff check .
uv run ty check
```
