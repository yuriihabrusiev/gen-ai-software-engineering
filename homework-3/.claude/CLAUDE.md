# Project Rules — Virtual Card Lifecycle

This is a regulated FinTech feature (virtual card issuance, freeze/unfreeze, limits, transaction visibility). Source of truth is `specification.md` (what/why, layered objectives and tasks) and `agents.md` (full agent contract). This file is the terse day-to-day ruleset — read it before touching any code in this project.

## Naming Conventions

- snake_case for all identifiers.
- Money fields end in `_minor` and are always paired with a currency code — never a bare number.
- Timestamp fields end in `_at`, stored and compared in UTC only.
- Card state values are exactly one of `PENDING`, `ACTIVE`, `FROZEN`, `CLOSED`, `EXPIRED` — no synonyms, no lowercase variants.

## Patterns To Follow

- One shared state-machine module owns every card state transition.
- One shared idempotency middleware handles all mutating endpoints.
- One shared audit-writer handles every `AuditEvent`; it must complete before a mutating call reports success.
- One shared RBAC layer enforces `cardholder:self` / `ops:support` / `ops:compliance` / `ops:fraud` scopes.

## Patterns To Avoid

- Don't add a second way to mutate card state (no direct field writes, no "quick fix" bypass of the state machine).
- Don't add PAN, CVV, or full card number fields anywhere — only `last4` and a token reference.
- Don't add a float or decimal type for money — integer minor units only.
- Don't invent a new error code family outside `VALIDATION_*`, `CONFLICT_*`, `PERMISSION_*`, `RATE_LIMITED_*`, `DOWNSTREAM_UNAVAILABLE_*`.

## FinTech-Sensitive Defaults

- Never log PAN, CVV, secrets, or full card numbers — at any log level, including debug.
- Money is always integer minor units + ISO 4217 currency code.
- Timestamps are UTC ISO-8601, generated server-side only.
- Idempotency keys are mandatory on every mutating action (create, freeze, unfreeze, limit update, close).
- Never bypass the state machine or the audit writer, even in error-handling or "temporary" code.

## What Not To Do

- No PII in logs, ever — this includes cardholder name, PAN, CVV, and full account numbers.
- No direct database writes to card state or limits that skip the audit-writer hook.
- No relaxing MFA/step-up requirements on high-risk ops actions for local development convenience — use a test double instead.
- No silent catch-and-continue on Issuing Processor errors — surface as `DOWNSTREAM_UNAVAILABLE_*`, never treat a timeout as a decline or an approval.
- No ad-hoc fixtures per test file — use the fixtures defined in `specification.md` (golden card set, synthetic decline set, synthetic fraud-pattern set).
