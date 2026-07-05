# Virtual Card Lifecycle Specification

> Ingest this specification and implement the Low-Level Tasks to satisfy the High-Level and Mid-Level Objectives. This document assumes a regulated FinTech environment (PCI DSS scope, financial recordkeeping, fraud-monitoring obligations) and is written to be implementable without further clarification.

## Domain Model (hypothetical entities referenced throughout)

| Entity | Description |
|---|---|
| `Cardholder` | End-user who owns a `FundingAccount` and can hold one or more virtual cards. |
| `VirtualCard` | A tokenized, non-physical card issued against a `FundingAccount`, with its own state and limits. |
| `FundingAccount` | Existing account (outside this feature's scope) that backs a virtual card's spending. |
| `CardLimitConfig` | Per-card limit configuration: per-transaction, daily, monthly ceilings; optional merchant-category restrictions. |
| `Transaction` | An authorization, hold, settlement, refund, or decline event tied to a `VirtualCard`. |
| `AuditEvent` | Immutable record of a state-changing action: actor, action, before/after state, timestamp, correlation ID. |
| `OpsActor` | Internal user in a support, compliance, or fraud role acting on a cardholder's behalf under RBAC. |

---

## High-Level Objective

Let a cardholder self-serve virtual card issuance, freeze/unfreeze control, and spend-limit management from a single control surface, while giving internal ops/compliance/fraud teams complete, tamper-evident visibility into every state change — **scoped strictly to card lifecycle, limits, and transaction visibility**; physical card fulfillment, card-network dispute arbitration, and cardholder KYC/onboarding are explicitly out of scope.

---

## Mid-Level Objectives

Each objective is observable — a reviewer can check whether it holds by looking at system state or output, not by reading code.

1. **MLO-1 — Card Issuance**: A cardholder can create a virtual card linked to a `FundingAccount`, and receives back a usable card identity (tokenized, last-4 visible) with default limits applied, in `PENDING` then `ACTIVE` state.
2. **MLO-2 — Freeze / Unfreeze**: A cardholder or authorized `OpsActor` can immediately block (`FREEZE`) or restore (`UNFREEZE`) a card's ability to authorize new transactions, with the effect observable in the next authorization decision.
3. **MLO-3 — Limit Management**: A cardholder can set or update per-transaction, daily, and monthly spend limits on their card, bounded by program-defined ceilings, and the new limits govern the next authorization.
4. **MLO-4 — Transaction Visibility**: A cardholder can retrieve a paginated, near-real-time list of their card's authorizations, holds, settlements, declines, and refunds.
5. **MLO-5 — Lifecycle State Integrity**: Every card strictly follows the state machine `PENDING → ACTIVE ⇄ FROZEN → CLOSED` (plus terminal `EXPIRED`); any other transition is rejected with a specific, stable error code.
6. **MLO-6 — Full Auditability**: Every state-changing action (issuance, freeze, unfreeze, limit change, closure) produces an immutable `AuditEvent` that ops/compliance can query without engineering assistance.
7. **MLO-7 — Fraud-Aware Guardrails**: Anomalous patterns (authorization velocity, rapid limit escalation, freeze/unfreeze thrashing) are detected and can trigger an automatic protective freeze, itself audited and notified to the cardholder.

---

## Non-Functional & Policy

### Security
- All card issuance and PAN resolution happens inside a hypothetical **Tokenization Vault**; this service never stores, logs, or transmits a full PAN or CVV. Only a masked representation (`•••• 4242`) and an internal token reference are held here.
- Data in transit is TLS 1.2+; data at rest is encrypted using the org's standard KMS-backed encryption.
- RBAC scopes are enforced per actor type: `cardholder:self` (own cards only), `ops:support` (view + freeze on behalf of a verified cardholder), `ops:compliance` (read-only + audit export), `ops:fraud` (freeze + limit override). No scope may act outside its defined boundary.
- High-risk `OpsActor` actions (unfreeze after a fraud-triggered freeze, limit override above program ceiling) require step-up authentication (MFA) within the preceding 5 minutes.

### Privacy
- Data minimization: only fields required for lifecycle/limit/transaction operations are stored in this service; identity/KYC data stays in the existing Identity service.
- Retention: transaction and audit records are retained for **7 years** to satisfy financial recordkeeping norms (see Implementation Notes for interaction with erasure requests).
- Right-to-erasure requests affecting a cardholder's PII are honored for display/profile data, but `AuditEvent` and `Transaction` records are retained under regulatory hold and instead anonymized (actor reference replaced with a redaction marker, financial facts preserved) — see Edge Cases.

### Audit / Logging
- Every mutating action writes an `AuditEvent` **synchronously and durably before** the triggering action returns success to the caller. A success response without a corresponding audit record must never be possible.
- Each `AuditEvent` captures: actor ID + role, action type, before-state, after-state, timestamp (UTC), and a correlation ID shared with the triggering request.
- Audit records are append-only; no update or delete path exists for them at the application layer.

### Reliability
- All mutating endpoints/operations (create, freeze, unfreeze, limit update, close) require and honor an idempotency key (see Implementation Notes).
- Transaction visibility (MLO-4) is near-real-time, not strictly consistent: a settlement event is guaranteed visible within 5 seconds (see Expected Performance).
- Availability targets: **99.95%** for freeze/unfreeze (fraud-critical path), **99.9%** for all other read/write paths, measured monthly.

### Performance
Latency budgets and throughput targets are defined once, in the dedicated **Expected Performance** section below, and referenced from here rather than duplicated.

---

## Implementation Notes (guardrails for builders/agents)

- **Money**: represented as an integer count of minor units (e.g. cents) plus an ISO 4217 currency code. Never use floating-point types for any monetary value.
- **IDs**: all entity IDs are ULIDs (sortable, collision-resistant). Card display surfaces show only the last 4 digits of the underlying PAN plus the token reference — never the full number.
- **Idempotency**: `create card`, `freeze`, `unfreeze`, `update limits`, and `close card` all require a client-supplied idempotency key.
  - Same key + same payload → return the original result (replay), no new side effect.
  - Same key + different payload → reject with `409 IDEMPOTENCY_KEY_CONFLICT`.
  - Keys expire after 24 hours.
- **Error taxonomy**: every error carries a stable machine-readable code in one of five families — `VALIDATION_*`, `CONFLICT_*`, `PERMISSION_*`, `RATE_LIMITED_*`, `DOWNSTREAM_UNAVAILABLE_*`. Agents must not invent ad-hoc error shapes outside this taxonomy.
- **State transitions**: enforced exclusively server-side via an explicit state machine; no client may set state directly, only request a transition (`freeze`, `unfreeze`, `close`).
- **Timestamps**: UTC, ISO-8601, generated server-side only — client-supplied timestamps are never trusted for ordering or audit purposes.
- **PCI DSS scope boundary**: this service operates outside full PCI DSS Level 1 cardholder-data-environment (CDE) scope by construction, because it never touches an unmasked PAN — that boundary must be preserved in any implementation (no debug logging of vault responses, no PAN fields added to this service's schema "for convenience").

---

## Context

### Beginning Context (hypothetical — exists before this work starts)
- Identity/Auth service (OIDC-based), already issuing cardholder and ops-actor identities.
- Ledger / `FundingAccount` service, already tracking account balances independent of card activity.
- Card Issuing Processor integration point — an external network capable of minting tokenized card identities and pushing authorization/settlement/decline events.
- Audit Event Bus — an existing durable event stream already consumed by other features for compliance reporting.
- Notification service — existing channel for pushing cardholder-facing alerts (push/email/SMS).
- None of the virtual-card-specific components below exist yet.

### Ending Context (state after this work is implemented)
- New `VirtualCard` service and its own data store (card records, state, timestamps).
- New `CardLimitConfig` store, versioned per change (for audit reconstruction).
- New Fraud Signal evaluator — a rules-based component consuming authorization events and emitting freeze recommendations.
- Documented integration contract with the Card Issuing Processor for card creation and inbound status/transaction events.
- An ops review queue surfacing fraud-flagged and MFA-gated actions for compliance follow-up.
- `AuditEvent`s for all virtual-card actions flowing into the existing Audit Event Bus, queryable by ops/compliance tooling already in place.
- This specification package as the artifact of record guiding the above.

---

## Low-Level Tasks

Each task lists what it does, the hypothetical component(s) it touches, which mid-level objective it serves, and acceptance criteria phrased so an implementer can check them off.

### MLO-1 — Card Issuance

**T1.1 — Define `VirtualCard` and `FundingAccount` link schema**
Component: `virtualcard-service` data model.
Serves: MLO-1, MLO-5.
Acceptance criteria:
- [ ] Schema includes `id` (ULID), `funding_account_id`, `state`, `created_at`, `token_reference`, `last4`, `currency`.
- [ ] No field capable of holding a full PAN or CVV exists anywhere in this schema.

**T1.2 — Implement card creation flow with idempotency**
Component: `virtualcard-service` create handler.
Serves: MLO-1.
Acceptance criteria:
- [ ] A request with a new idempotency key creates exactly one card in `PENDING` state, then transitions to `ACTIVE` once the issuing processor confirms tokenization.
- [ ] A replayed request (same key, same payload) returns the original card without creating a duplicate.
- [ ] A conflicting request (same key, different payload) returns `409 IDEMPOTENCY_KEY_CONFLICT`.

**T1.3 — Apply default `CardLimitConfig` on issuance**
Component: `virtualcard-service` + `CardLimitConfig` store.
Serves: MLO-1, MLO-3.
Acceptance criteria:
- [ ] Every newly issued card has a `CardLimitConfig` row created atomically with the card record (same transaction or compensating action on failure).
- [ ] Default limits match the program's published defaults; no card is ever issued with null/undefined limits.

**T1.4 — Emit `AuditEvent` on card creation**
Component: `virtualcard-service` → Audit Event Bus.
Serves: MLO-1, MLO-6.
Acceptance criteria:
- [ ] The audit write completes and is durably confirmed before the create call returns success to the caller.
- [ ] The event includes actor ID, `funding_account_id`, resulting card ID, and correlation ID.

### MLO-2 — Freeze / Unfreeze

**T2.1 — Implement freeze operation**
Component: `virtualcard-service` state transition handler.
Serves: MLO-2, MLO-5.
Acceptance criteria:
- [ ] `ACTIVE → FROZEN` succeeds; any other source state is rejected with `CONFLICT_INVALID_TRANSITION`.
- [ ] Once frozen, any authorization request against the card is declined by the next authorization check with no observable delay beyond the stated latency budget.

**T2.2 — Implement unfreeze operation with role check**
Component: `virtualcard-service` state transition handler + RBAC layer.
Serves: MLO-2, MLO-7.
Acceptance criteria:
- [ ] `FROZEN → ACTIVE` succeeds for the cardholder unless the freeze was fraud-triggered, in which case only `ops:fraud` with a valid MFA step-up may unfreeze.
- [ ] An unauthorized unfreeze attempt returns `PERMISSION_DENIED` and produces an `AuditEvent` recording the denied attempt.

**T2.3 — Support ops-initiated freeze on behalf of a cardholder**
Component: `virtualcard-service` + support tooling.
Serves: MLO-2, MLO-6.
Acceptance criteria:
- [ ] `ops:support` and `ops:fraud` can freeze any card; the resulting `AuditEvent` records the acting `OpsActor` distinctly from cardholder-initiated freezes.

**T2.4 — Guard against freeze/unfreeze thrashing**
Component: `virtualcard-service` rate limiter.
Serves: MLO-2, MLO-7.
Acceptance criteria:
- [ ] More than 20 freeze/unfreeze calls per card per minute is rejected with `RATE_LIMITED_TOGGLE` and logged as a fraud signal input.

### MLO-3 — Limit Management

**T3.1 — Implement limit update with program-ceiling validation**
Component: `virtualcard-service` + `CardLimitConfig` store.
Serves: MLO-3.
Acceptance criteria:
- [ ] A limit update is rejected with `VALIDATION_LIMIT_OUT_OF_RANGE` if any value is negative, zero (for per-transaction/daily/monthly caps that must be positive), or exceeds the program-defined ceiling.
- [ ] A valid update creates a new versioned `CardLimitConfig` row rather than mutating the previous one in place.

**T3.2 — Enforce limits at authorization time**
Component: authorization decision path (integration with Issuing Processor).
Serves: MLO-3, MLO-5.
Acceptance criteria:
- [ ] An authorization exceeding the currently active per-transaction, daily, or monthly limit is declined with a decline reason mapped to the specific limit breached.
- [ ] A limit change takes effect for the very next authorization decision (see Expected Performance for the consistency budget).

**T3.3 — Handle limit lowered below existing pending holds**
Component: `virtualcard-service` limit update handler.
Serves: MLO-3, MLO-5 (see also Edge Cases).
Acceptance criteria:
- [ ] Lowering a limit below the sum of currently pending holds does not retroactively cancel those holds; it only affects future authorizations.
- [ ] The response to the limit-update call includes a warning field noting the existing holds exceed the new limit.

**T3.4 — Emit `AuditEvent` with before/after limit diff**
Component: `virtualcard-service` → Audit Event Bus.
Serves: MLO-3, MLO-6.
Acceptance criteria:
- [ ] The audit record includes the full before and after `CardLimitConfig` values, not just a change flag.

### MLO-4 — Transaction Visibility

**T4.1 — Implement paginated transaction listing**
Component: `virtualcard-service` read API (hypothetical).
Serves: MLO-4.
Acceptance criteria:
- [ ] Supports cursor-based pagination; default page size 20, maximum 100.
- [ ] Results are ordered newest-first by event timestamp, not insertion order.

**T4.2 — Reflect authorization/hold/settlement/decline/refund types distinctly**
Component: `Transaction` read model.
Serves: MLO-4.
Acceptance criteria:
- [ ] Each transaction row exposes a `type` field with exactly one of the five defined values; no ambiguous or combined types.

**T4.3 — Label stale data during processor outage**
Component: `virtualcard-service` read API + processor health check.
Serves: MLO-4 (see also Edge Cases).
Acceptance criteria:
- [ ] When the Issuing Processor feed is degraded, the transaction listing response includes a `data_freshness` field (`live` or `stale_since: <timestamp>`) rather than failing the request outright.

**T4.4 — Handle pagination cursor invalidation under concurrent writes**
Component: `virtualcard-service` read API.
Serves: MLO-4 (see also Edge Cases).
Acceptance criteria:
- [ ] An expired/invalidated cursor returns `VALIDATION_CURSOR_EXPIRED` rather than silently returning wrong or duplicate results.

### MLO-5 — Lifecycle State Integrity

**T5.1 — Implement the full state machine as a single enforced module**
Component: `virtualcard-service` state machine module.
Serves: MLO-5.
Acceptance criteria:
- [ ] All valid transitions (`PENDING→ACTIVE`, `ACTIVE⇄FROZEN`, `ACTIVE/FROZEN→CLOSED`, any state `→EXPIRED` on expiry date) are enumerated in one place; no other code path mutates card state directly.
- [ ] An attempted invalid transition (e.g. `CLOSED→ACTIVE`) is rejected with `CONFLICT_INVALID_TRANSITION` and never partially applied.

**T5.2 — Implement card closure with unsettled-transaction check**
Component: `virtualcard-service` close handler.
Serves: MLO-5 (see also Edge Cases).
Acceptance criteria:
- [ ] Closing a card with unsettled (pending) transactions is allowed but the card enters `CLOSED` with a documented flag `has_pending_settlement: true`; new authorizations are blocked immediately regardless.

**T5.3 — Implement card expiry as a scheduled transition**
Component: `virtualcard-service` scheduled job.
Serves: MLO-5.
Acceptance criteria:
- [ ] A card past its `expires_at` timestamp transitions to `EXPIRED` within 1 hour of expiry, blocking new authorizations, independent of any user action.

**T5.4 — Concurrency-safe state transitions**
Component: `virtualcard-service` state machine module.
Serves: MLO-5 (see also Edge Cases).
Acceptance criteria:
- [ ] Two concurrent transition requests on the same card (e.g. simultaneous freeze + unfreeze) are serialized (optimistic locking or equivalent); exactly one succeeds, the other receives `CONFLICT_STATE_CHANGED` and must re-read current state before retrying.

### MLO-6 — Full Auditability

**T6.1 — Build the shared audit-writer component**
Component: new `audit-writer` module used by all mutating handlers.
Serves: MLO-6.
Acceptance criteria:
- [ ] No mutating handler calls the Audit Event Bus directly; all go through `audit-writer`, which guarantees durability before returning.
- [ ] `audit-writer` failures cause the triggering action to fail as well (no action succeeds without its audit record).

**T6.2 — Provide ops/compliance audit query access**
Component: audit query surface (hypothetical, read-only).
Serves: MLO-6.
Acceptance criteria:
- [ ] `ops:compliance` can query all `AuditEvent`s for a given card or cardholder without needing engineering assistance or direct database access.

**T6.3 — Redact-not-delete on erasure requests**
Component: `audit-writer` + erasure handler.
Serves: MLO-6 (see also Edge Cases, Non-Functional & Policy: Privacy).
Acceptance criteria:
- [ ] An erasure request replaces the actor's PII in historical `AuditEvent`s with a redaction marker while preserving the financial facts (amounts, timestamps, state transitions) unchanged.

### MLO-7 — Fraud-Aware Guardrails

**T7.1 — Implement velocity-based fraud signal**
Component: new Fraud Signal evaluator.
Serves: MLO-7.
Acceptance criteria:
- [ ] A configurable threshold (e.g. more than N authorizations within M minutes) triggers a fraud signal without blocking the underlying authorizations that already succeeded.

**T7.2 — Implement automatic protective freeze on high-confidence signal**
Component: Fraud Signal evaluator → `virtualcard-service`.
Serves: MLO-7, MLO-2, MLO-5, MLO-6.
Acceptance criteria:
- [ ] A high-confidence fraud signal transitions the card `ACTIVE→FROZEN` automatically, writes an `AuditEvent` with actor `system:fraud-evaluator`, and triggers a cardholder notification within the performance budget.

**T7.3 — Route fraud-triggered freezes to the ops review queue**
Component: ops review queue (hypothetical).
Serves: MLO-7, MLO-6.
Acceptance criteria:
- [ ] Every automatic freeze appears in the review queue within 1 minute, with the triggering signal data attached for `ops:fraud` review.

### Cross-Cutting Tasks

**TX.1 — Idempotency-key middleware**
Component: shared middleware used by all mutating endpoints.
Serves: MLO-1, MLO-2, MLO-3, MLO-5.
Acceptance criteria:
- [ ] A single, shared implementation is used everywhere idempotency is required; no handler reimplements key comparison logic independently.

**TX.2 — RBAC scope enforcement layer**
Component: shared authorization middleware.
Serves: MLO-2, MLO-3, MLO-6, Non-Functional & Policy: Security.
Acceptance criteria:
- [ ] Every mutating and audit-query call passes through this layer; scope checks cannot be bypassed by calling an internal function directly (enforced at the same boundary for all callers).

**TX.3 — Standard error-response formatting**
Component: shared error-handling layer.
Serves: Implementation Notes: Error Taxonomy.
Acceptance criteria:
- [ ] Every error response across all endpoints uses the five-family code taxonomy; a lint/review check flags any new ad-hoc error code.

**TX.4 — Reconciliation batch job**
Component: nightly batch process.
Serves: MLO-4, MLO-6, Verification.
Acceptance criteria:
- [ ] Compares `Transaction` totals in this service against `FundingAccount` ledger postings for the same period and reports any discrepancy above a defined tolerance to `ops:compliance`.

---

## Edge Cases & Failure Modes

| Scenario | Trigger | Expected Behavior | Audit/Compliance Implication |
|---|---|---|---|
| Duplicate create request | Client retries a create call after a timeout, same idempotency key | Original card returned, no duplicate created (T1.2) | Single audit record; retry is not logged as a separate action |
| Freeze during in-flight authorization | Freeze issued while an authorization is mid-flight at the processor | In-flight authorization completes per its own outcome; only subsequent authorizations are blocked | Audit record timestamps make the ordering reconstructable |
| Limit lowered below pending holds | Cardholder reduces daily limit after holds already exceed it | Existing holds unaffected; response carries a warning field (T3.3) | Audit diff shows old/new limit and the outstanding-holds warning |
| Concurrent freeze + unfreeze | Two requests race on the same card | Exactly one succeeds via optimistic locking; the other gets `CONFLICT_STATE_CHANGED` (T5.4) | Both attempts are audited; only one produces a state change |
| Close card with unsettled transactions | Cardholder closes a card with a pending settlement | Card closes with `has_pending_settlement: true`; new authorizations blocked immediately (T5.2) | Ops/compliance can filter closed cards with pending settlements for follow-up |
| Transaction view during processor outage | Issuing Processor feed degraded/unavailable | Listing still returns, with `data_freshness: stale_since: <ts>` rather than an error (T4.3) | No silent data loss; staleness itself is auditable via the health-check log |
| Invalid/negative/over-ceiling limit | Cardholder submits a negative or above-program-ceiling limit | Rejected with `VALIDATION_LIMIT_OUT_OF_RANGE`; no partial update (T3.1) | Rejected attempts are not treated as state changes; not audited as a limit change |
| Ops action without required role/MFA | `ops:support` attempts a fraud-gated unfreeze without MFA | Rejected with `PERMISSION_DENIED` (T2.2) | Denied attempt itself is audited for compliance monitoring of access-control effectiveness |
| Fraud velocity pattern | Authorization rate exceeds configured threshold | Automatic protective freeze (T7.2), cardholder notified, ops review queued (T7.3) | Full signal data retained alongside the freeze `AuditEvent` |
| Card expiry during open dispute | Card's `expires_at` passes while a related dispute is unresolved | Card still transitions to `EXPIRED` (state and disputes are independent); dispute continues against transaction history, not live card state | Audit trail remains queryable after expiry — expiry does not remove history |
| Idempotency key reused, different payload | Client bug resends a create/update with the same key but changed fields | Rejected with `409 IDEMPOTENCY_KEY_CONFLICT`; original result untouched (T1.2) | No new audit record; the conflict itself may optionally be logged at the infra level, not as a domain audit event |
| Statement-period boundary at DST transition | Daily limit window crosses a DST shift | Daily windows are computed in UTC, not local time, so DST has no effect on limit-window boundaries | N/A — documented in Implementation Notes to prevent future ambiguity |
| Pagination cursor invalidated by concurrent writes | New transactions arrive while a client pages through results | Expired cursor returns `VALIDATION_CURSOR_EXPIRED` rather than skipped/duplicated rows (T4.4) | No compliance impact; purely a read-consistency concern |
| Erasure request vs. regulatory hold | Cardholder requests data erasure while records are under the 7-year retention hold | PII redacted in place; financial facts and audit trail preserved under the hold (T6.3) | Compliance can demonstrate the retention hold was honored despite the erasure request |

---

## Verification

Verification depth is scaled to risk: state-changing and compliance-sensitive flows (freeze, limit change, closure, audit) get the heaviest coverage; read-only visibility gets lighter coverage focused on correctness and pagination behavior.

| Mid-Level Objective | Unit | Integration | E2E / Manual | Reconciliation / Compliance |
|---|---|---|---|---|
| MLO-1 Issuance | State-machine transitions, default-limit application | Idempotency replay/conflict against a processor stub | Full create-to-active flow against a sandboxed processor | — |
| MLO-2 Freeze/Unfreeze | RBAC scope checks, rate-limit thresholds | Freeze effect observable in next authorization stub call | Manual QA: freeze then attempt a purchase, confirm decline | Ops sampling of a random set of freezes/unfreezes per week |
| MLO-3 Limits | Ceiling validation, versioning of `CardLimitConfig` | Limit enforcement at authorization-stub time | Manual QA: lower limit mid-cycle, confirm pending holds unaffected | — |
| MLO-4 Transactions | Pagination boundary conditions, cursor expiry | Stale-data labeling against a simulated processor outage | Manual QA: page through a large synthetic transaction set | Nightly reconciliation batch (TX.4) vs. ledger postings |
| MLO-5 State Integrity | Every transition in the state machine (valid and invalid) | Concurrency test: two simultaneous transition requests | — | — |
| MLO-6 Auditability | Audit-writer durability guarantee (failure = action failure) | Full audit trail reconstruction for a multi-step scenario | Ops/compliance walkthrough: query audit trail for a sample card without engineering help | Quarterly compliance review of a sampled audit export |
| MLO-7 Fraud Guardrails | Threshold evaluation logic | Automatic freeze end-to-end against synthetic velocity fixture | Manual QA: simulate a fraud pattern, confirm freeze + notification + queue entry | Ops:fraud review queue triage SLA tracked monthly |

**Required fixtures**: a "golden" set of cards spanning every lifecycle state, a synthetic decline set (one per decline reason), a synthetic fraud-pattern set (velocity, limit-escalation, thrash patterns), and a processor-outage simulation harness for staleness testing.

**Definition of done** for this specification's objectives is primarily carried by the inline acceptance criteria on each Low-Level Task above; this table is the cross-cutting index tying objectives to test category, not a replacement for those checklists.

---

## Expected Performance

All figures below are **assumed targets** for planning purposes, each justified against FinTech UX or regulatory-examination norms; they should be revisited against real traffic once implemented.

| Operation | Target | Why |
|---|---|---|
| Freeze / unfreeze (end-to-end) | p95 < 300 ms | A cardholder or fraud responder needs the block to feel immediate; delay directly extends fraud exposure window. |
| Freeze propagation to Issuing Processor block list | p99 < 2 s | Bounds the worst-case window during which a new authorization could still slip through post-freeze. |
| Card creation | p95 < 800 ms | Involves a synchronous processor call; acceptable to be slower than freeze but still within a single user-perceived action. |
| Limit create/update | p95 < 400 ms; effective for next authorization within 1 s | Cardholders expect a limit change to "stick" before they attempt the next purchase. |
| Transaction list read | p95 < 250 ms; page size max 100, default 20 | Read-heavy path; bounding page size protects backend latency and keeps client rendering predictable. |
| Time-to-consistency for new transactions | Visible within 5 s of settlement event | Documented as near-real-time, not synchronous — avoids over-promising strict consistency on an eventually-consistent feed. |
| Audit write durability | Durable before triggering action returns success; p95 < 150 ms for the write itself | Regulatory examination requires that no state change can exist without a corresponding audit record. |
| Nightly reconciliation batch | Up to 5,000,000 transactions processed within a 2-hour window | Sized to complete well before the next business day's operations begin. |
| Rate limit: freeze/unfreeze | Max 20 calls/min/card | Prevents thrash abuse while comfortably exceeding any legitimate use pattern. |
| Rate limit: limit updates | Max 10 calls/min/card | Same rationale, scaled to the lower expected frequency of limit changes. |
| Availability: freeze/unfreeze path | 99.95% monthly | Fraud-critical path; higher target than general read/write availability. |
| Availability: all other paths | 99.9% monthly | Standard target consistent with typical FinTech customer-facing SLOs. |
