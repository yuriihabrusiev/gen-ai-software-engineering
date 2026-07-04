# Homework 3 — Virtual Card Lifecycle Specification

> **Student Name**: Yurii Habrusiev
> **Date Submitted**: 2026-07-05
> **AI Tools Used**: Claude Code (Sonnet 5)

---

This submission is a specification-only package for a virtual card lifecycle feature: issuance, freeze/unfreeze, spend-limit management, and transaction visibility, built for a regulated FinTech environment with an internal ops/compliance view alongside the end-user. No code, APIs, or UI were implemented, per the assignment's scope. Virtual card lifecycle was chosen over the other seed options because it exercises the widest range of regulated-FinTech concerns in one coherent feature: tokenized-PAN handling, state-machine integrity, fraud-triggered automated actions, and audit requirements that all interact with each other rather than sitting in isolation.

The package consists of four files: `specification.md` (the layered spec), `agents.md` (AI agent contract for a future implementation), `.claude/CLAUDE.md` (terse day-to-day editor rules), and this `README.md`.

## Rationale

The specification is organized as a strict top-down funnel — High-Level Objective → Mid-Level Objectives → Non-Functional & Policy → Implementation Notes → Context → Low-Level Tasks — so that every low-level task is traceable back to the mid-level objective it serves (each task in `specification.md` states this explicitly, e.g. "Serves: MLO-2, MLO-5"). This traceability was prioritized over prose length: the assignment grades decomposition and traceability, not word count, so tasks are kept short and acceptance-criteria-driven rather than narrative.

Verification depth was scaled to risk rather than applied uniformly. State-changing and compliance-sensitive flows — freeze/unfreeze, limit changes, closure, and the audit trail itself — carry unit, integration, and manual/ops-review coverage plus periodic compliance sampling, because an error there has a direct regulatory or fraud-exposure cost. Read-only transaction visibility carries lighter coverage focused on correctness and pagination edge cases, since an error there is a UX annoyance rather than a compliance incident. This asymmetry is stated explicitly at the top of the Verification section in `specification.md` so it reads as a deliberate choice, not an oversight.

Performance targets are labeled "assumed targets" throughout and each carries a one-line justification rather than a bare number, because the assignment explicitly allows hypothetical figures as long as they're reasoned. The reasoning generally follows two patterns: (1) fraud-adjacent operations (freeze/unfreeze) get the tightest budgets because delay directly extends a fraud-exposure window, and (2) durability-critical operations (the audit write) are specified as "durable before success is returned" rather than a pure latency number, because the regulatory requirement is about guarantee, not speed.

## Industry Best Practices

| Practice | Where It Appears |
|---|---|
| PCI DSS scope minimization via tokenization (never store/log a full PAN) | `specification.md` → Implementation Notes, Non-Functional & Policy: Security; `agents.md` → Domain Rules, Security & Compliance Constraints; `.claude/CLAUDE.md` → FinTech-Sensitive Defaults |
| Immutable, synchronous audit trail before success response | `specification.md` → Non-Functional & Policy: Audit/Logging, Low-Level Tasks T1.4/T3.4/T6.1; `agents.md` → Domain Rules, Testing & Verification Expectations |
| Idempotent writes on all mutating operations | `specification.md` → Implementation Notes, Low-Level Task TX.1; `agents.md` → Domain Rules; `.claude/CLAUDE.md` → FinTech-Sensitive Defaults |
| Role-based access control with least privilege per actor type | `specification.md` → Non-Functional & Policy: Security, Low-Level Task TX.2; `agents.md` → Security & Compliance Constraints |
| Explicit, closed error taxonomy (no ad-hoc error shapes) | `specification.md` → Implementation Notes, Low-Level Task TX.3; `agents.md` → Code Style; `.claude/CLAUDE.md` → Patterns To Avoid |
| Fail-safe defaults under ambiguity (freeze over allow) | `agents.md` → Edge Case Handling Directives; `specification.md` → Edge Cases & Failure Modes table |
| Money as integer minor units, never floating point | `specification.md` → Implementation Notes; `agents.md` → Domain Rules; `.claude/CLAUDE.md` → What Not To Do |
| Redact-not-delete for erasure requests under regulatory hold | `specification.md` → Non-Functional & Policy: Privacy, Edge Cases table, Low-Level Task T6.3 |
| Reconciliation between service records and the source ledger | `specification.md` → Low-Level Task TX.4, Verification table |
| Risk-scaled verification depth (heavier coverage for compliance-sensitive flows) | `specification.md` → Verification section |

<div align="center">

*This project was completed as part of the AI-Assisted Development course.*

</div>
