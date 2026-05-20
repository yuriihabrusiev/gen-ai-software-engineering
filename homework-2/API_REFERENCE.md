# API Reference

Audience: API consumers integrating with the Customer Support Ticket API.

Base URL for local development:

```text
http://127.0.0.1:8000
```

## Data Models

### TicketCreate

```json
{
  "customer_id": "cust-001",
  "customer_email": "customer@example.com",
  "customer_name": "Ada Lovelace",
  "subject": "Cannot access my account",
  "description": "I cannot access my account after resetting my password.",
  "category": "account_access",
  "priority": "medium",
  "status": "new",
  "assigned_to": null,
  "tags": ["login", "password"],
  "metadata": {
    "source": "web_form",
    "browser": "Chrome",
    "device_type": "desktop"
  }
}
```

Required fields: `customer_id`, `customer_email`, `customer_name`, `subject`, and `description`.

Allowed values:

- `category`: `account_access`, `technical_issue`, `billing_question`, `feature_request`, `bug_report`, `other`
- `priority`: `urgent`, `high`, `medium`, `low`
- `status`: `new`, `in_progress`, `waiting_customer`, `resolved`, `closed`
- `metadata.source`: `web_form`, `email`, `api`, `chat`, `phone`
- `metadata.device_type`: `desktop`, `mobile`, `tablet`

### TicketResponse

```json
{
  "id": "bce3f587-7415-4b02-b9b3-94d1a44f7607",
  "customer_id": "cust-001",
  "customer_email": "customer@example.com",
  "customer_name": "Ada Lovelace",
  "subject": "Cannot access my account",
  "description": "I cannot access my account after resetting my password.",
  "category": "account_access",
  "priority": "urgent",
  "status": "new",
  "created_at": "2026-05-21T10:15:30.000000+00:00",
  "updated_at": "2026-05-21T10:15:30.000000+00:00",
  "resolved_at": null,
  "assigned_to": null,
  "tags": ["login", "password"],
  "metadata": {
    "source": "web_form",
    "browser": "Chrome",
    "device_type": "desktop"
  },
  "classification_confidence": 0.7
}
```

## Error Format

FastAPI validation errors use HTTP `422`:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "description"],
      "msg": "String should have at least 10 characters",
      "input": "short"
    }
  ]
}
```

Application errors use `detail`:

```json
{
  "detail": "Ticket not found"
}
```

## Endpoints

### Create Ticket

`POST /tickets`

Optional query parameter: `auto_classify=true`.

```bash
curl -X POST "http://127.0.0.1:8000/tickets?auto_classify=true" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "cust-001",
    "customer_email": "customer@example.com",
    "customer_name": "Ada Lovelace",
    "subject": "Cannot access my account",
    "description": "I cannot access my account after resetting my password.",
    "tags": ["login"],
    "metadata": {"source": "web_form", "browser": "Chrome", "device_type": "desktop"}
  }'
```

Success: `201 Created` with `TicketResponse`.

### List Tickets

`GET /tickets`

Optional query parameters: `status`, `category`, `priority`.

```bash
curl "http://127.0.0.1:8000/tickets?status=new&category=account_access&priority=urgent"
```

Success: `200 OK` with an array of `TicketResponse`.

### Get Ticket

`GET /tickets/{ticket_id}`

```bash
curl "http://127.0.0.1:8000/tickets/bce3f587-7415-4b02-b9b3-94d1a44f7607"
```

Success: `200 OK` with `TicketResponse`.

Not found: `404 Not Found`.

### Update Ticket

`PUT /tickets/{ticket_id}`

The body is a partial update. Send only fields that should change.

```bash
curl -X PUT "http://127.0.0.1:8000/tickets/bce3f587-7415-4b02-b9b3-94d1a44f7607" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "resolved",
    "assigned_to": "agent-42"
  }'
```

Success: `200 OK` with `TicketResponse`. When `status` changes to `resolved`, `resolved_at` is set automatically.

### Delete Ticket

`DELETE /tickets/{ticket_id}`

```bash
curl -X DELETE "http://127.0.0.1:8000/tickets/bce3f587-7415-4b02-b9b3-94d1a44f7607"
```

Success: `204 No Content`.

### Auto-Classify Ticket

`POST /tickets/{ticket_id}/auto-classify`

```bash
curl -X POST "http://127.0.0.1:8000/tickets/bce3f587-7415-4b02-b9b3-94d1a44f7607/auto-classify"
```

Success:

```json
{
  "category": "account_access",
  "priority": "urgent",
  "confidence": 0.7,
  "reasoning": "Category 'account_access' matched keywords: password, account. Priority 'urgent' matched keywords: cannot access.",
  "keywords_found": ["password", "account", "cannot access"]
}
```

The classification is also applied to the stored ticket.

### Import Tickets

`POST /tickets/import`

Optional query parameter: `auto_classify=true` applies the keyword classifier to each
successfully imported ticket before returning the import summary.

CSV:

```bash
curl -X POST "http://127.0.0.1:8000/tickets/import" \
  -F "file=@tests/fixtures/sample_tickets.csv;type=text/csv"
```

JSON:

```bash
curl -X POST "http://127.0.0.1:8000/tickets/import" \
  -F "file=@tests/fixtures/sample_tickets.json;type=application/json"
```

XML:

```bash
curl -X POST "http://127.0.0.1:8000/tickets/import" \
  -F "file=@tests/fixtures/sample_tickets.xml;type=application/xml"
```

CSV with auto-classification:

```bash
curl -X POST "http://127.0.0.1:8000/tickets/import?auto_classify=true" \
  -F "file=@tests/fixtures/sample_tickets.csv;type=text/csv"
```

Success:

```json
{
  "total": 3,
  "successful": 2,
  "failed": 1,
  "errors": [
    {
      "row": 3,
      "error": "customer_email: value is not a valid email address"
    }
  ]
}
```

Malformed JSON or XML returns `400 Bad Request`. Unsupported file types return `415 Unsupported Media Type`.
