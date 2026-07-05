# AGENTS.md — Virtual Card Lifecycle

## Purpose

This file guides an AI coding agent if and when `specification.md` is implemented. It is not itself an implementation and assumes no code exists yet. Where this file and `specification.md` disagree, `specification.md` is authoritative — this file restates the parts an agent must never violate while writing code.

## Assumed Tech Stack

| Layer | Assumption | Notes |
|---|---|---|
| Language / runtime | Python 3.12+ | Consistent with this course's established toolchain; swappable if the implementer chooses otherwise. |
| Web framework | FastAPI | Matches prior homework conventions; any framework must preserve the error taxonomy and idempotency contract below. |
| Primary data store | PostgreSQL | Needs transactional guarantees for atomic card+limit creation (T1.3) and optimistic locking (T5.4). |
| Audit sink | Append-only table or existing Audit Event Bus | Must be write-only from the application's perspective — no update/delete code path. |
| Test runner | pytest | Unit, integration, and contract test tiers as described in `specification.md`'s Verification section. |
| Tooling | uv / mise | Dependency and task-runner conventions consistent with this course's prior homeworks. |

## Domain Rules (non-negotiable)

- The card state machine (`PENDING → ACTIVE ⇄ FROZEN → CLOSED`, plus `EXPIRED`) lives in exactly one module. No other code path may set card state directly.
- Money is always an integer minor-units value plus an ISO 4217 currency code. Never introduce a float or decimal-with-rounding-ambiguity type for money.
- A full PAN or CVV is never a field in this service's schema, logs, or API responses. Only `last4` and an opaque `token_reference` from the vault are permitted.
- All mutating operations (create, freeze, unfreeze, limit update, close) require and validate an idempotency key per the replay/conflict semantics in `specification.md`'s Implementation Notes.
- An `AuditEvent` write is mandatory and must complete before any mutating action reports success. If the audit write fails, the triggering action fails too.

## Code Style

- snake_case for identifiers; money fields end in `_minor` (e.g. `limit_daily_minor`); timestamp fields end in `_at` and are always UTC.
- All IDs are ULIDs generated server-side; never accept a client-supplied ID for a new entity.
- Error responses use only the five documented code families (`VALIDATION_*`, `CONFLICT_*`, `PERMISSION_*`, `RATE_LIMITED_*`, `DOWNSTREAM_UNAVAILABLE_*`). Do not invent a new family without updating `specification.md`.
- Prefer explicit, named state-transition functions (`freeze_card`, `unfreeze_card`) over a generic `update_state(new_state)` entry point — the former makes invalid transitions a compile-time/type-level concern, the latter does not.

## Testing & Verification Expectations

Map new code to the Verification table in `specification.md` before considering a task done:

- Every state transition (valid and invalid) in the state machine needs a unit test — this is the highest-value, cheapest test in this domain.
- Idempotency replay and conflict behavior needs an integration test per mutating endpoint, not just one shared example.
- Any change touching limits or freeze/unfreeze needs a test asserting the effect is observable in the *next* authorization decision, not just that a database row changed.
- Audit-writer failure must be tested as a failure-injection case: confirm the triggering action itself fails when the audit write fails.
- Use the fixtures named in `specification.md` (golden card set, synthetic decline set, synthetic fraud-pattern set) rather than inventing ad-hoc fixtures per test file.

## Security & Compliance Constraints

- Never log a PAN, CVV, or full card number at any log level, including debug. Log only `last4` and the token reference.
- Enforce RBAC scopes (`cardholder:self`, `ops:support`, `ops:compliance`, `ops:fraud`) at a single shared middleware/decorator layer — never re-implement a scope check inline in a handler.
- High-risk ops actions (unfreeze after a fraud-triggered freeze, limit override above program ceiling) require a valid MFA step-up within 5 minutes; do not relax this for convenience during development — use a test double for MFA in tests instead of bypassing the check in application code.
- Erasure requests redact PII in historical audit records but never delete the record itself; financial facts and state-transition history must remain intact under the 7-year retention hold.

## Edge Case Handling Directives

- When uncertain whether an authorization should be allowed or blocked (e.g. ambiguous fraud signal, degraded processor state), **prefer the fail-safe direction**: block/freeze rather than allow. A false-positive freeze is recoverable by a human; a false-negative fraud allowance may not be.
- Never silently swallow a timeout or error from the Issuing Processor. Surface it as a `DOWNSTREAM_UNAVAILABLE_*` error so callers can distinguish "declined" from "we don't know."
- Always require and validate idempotency keys on mutating operations — do not add an "internal" or "trusted caller" bypass path.
- Never bypass the audit writer, including on error paths where an operation partially succeeded (e.g. a limit was updated but the notification failed) — the partial state itself is auditable.
- When a limit update would leave existing pending holds over the new limit, do not retroactively cancel those holds; surface a warning instead (see `specification.md` T3.3).

## Adding New Features

1. Add or update the relevant Mid-Level Objective in `specification.md` first — a new capability without an observable objective is a scope-creep smell.
2. Write the Low-Level Task(s) with acceptance criteria before writing code; if a task can't be phrased as a checkable acceptance criterion, it's too vague to implement yet.
3. Check the Edge Cases table for a scenario this feature might introduce (concurrency, partial failure, permission boundary) and add a row if one is missing.
4. Confirm the new capability's mutating actions go through the existing idempotency middleware and audit-writer rather than adding parallel implementations.
5. Add the corresponding row to the Verification table, scaled to risk (state-changing/compliance-sensitive → heavier coverage).
