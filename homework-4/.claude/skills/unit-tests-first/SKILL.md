---
description: Defines the FIRST principles (Fast, Independent, Repeatable, Self-validating, Timely) and a concrete checklist for writing high-quality unit tests. Use whenever generating or reviewing unit tests.
---

# Unit Tests: FIRST Principles

A quality bar for unit tests, expressed as five properties every test must satisfy:
**F**ast, **I**ndependent, **R**epeatable, **S**elf-validating, **T**imely. Use this
skill any time you are writing or reviewing unit tests — do not invent an ad hoc
quality bar. A test that violates any one of these letters is not done, even if it
currently passes.

## F — Fast

**What it means**: A unit test exercises a small unit of logic in memory and
completes in milliseconds. A fast suite gets run constantly; a slow one gets
skipped.

**Common violations**:
- Hitting a real database, filesystem, network, or external API.
- Sleeping or polling (`sleep(2)`, retry loops with real delays) to wait for
  something to become true.
- Spinning up a real server, container, or browser for what is really a logic
  check.
- Loading large fixtures or datasets when a minimal example would prove the
  same point.

**Concrete check**: Before writing the test, confirm every dependency is either
pure in-memory logic or a fake/stub/mock. If the test would need network access,
disk I/O, or a wall-clock sleep to pass, replace that dependency or push the test
down to a smaller unit. A single test or small file of tests should run in well
under a second.

## I — Independent

**What it means**: Each test sets up its own state, exercises the code, and
asserts on the outcome without relying on any other test having run first (or in
a particular order), and without leaking state that affects tests that run after
it.

**Common violations**:
- Test B asserts on data left behind by test A (shared fixture never reset).
- Tests mutate a shared module-level variable, singleton, cache, or global
  config and never restore it.
- Tests are written assuming a specific execution order (e.g., "test_1_create"
  before "test_2_delete").
- Shared mutable test doubles (e.g., one mock object reused across tests
  without resetting call counts/state).

**Concrete check**: For each test, ask "if I ran only this test in isolation,
or ran all tests in a shuffled/random order, would it still pass?" If the
answer depends on another test's side effects, fix it — construct fresh
fixtures/state in setup (or inline in the test) and tear down or reset any
shared/global state the test touches, even if the framework doesn't force
teardown.

## R — Repeatable

**What it means**: A test produces the same result every time it runs, in any
environment (a developer's machine, CI, a colleague's laptop), regardless of
when or how many times it's run.

**Common violations**:
- Asserting against the current wall-clock time, `Date.now()`, or system
  timezone without freezing/injecting a fixed clock.
- Relying on random values, UUIDs, or iteration order of unordered
  collections (e.g., hash maps/sets) without seeding or sorting.
- Depending on environment variables, locale, or machine-specific paths that
  aren't controlled by the test.
- Leftover state from a previous run on disk (e.g., a file the test appends
  to without resetting it first).

**Concrete check**: Identify every source of non-determinism the changed code
touches (time, randomness, ordering, environment) and pin it explicitly —
inject/mock a fixed clock, seed random generators or replace them with fixed
values, sort before asserting on collection contents, and clean up any created
files/state within the test itself. If a source of non-determinism can't be
pinned, the test is not repeatable and must be redesigned.

## S — Self-validating

**What it means**: The test itself produces an unambiguous pass/fail signal via
assertions — no human has to read log output or inspect a printout to know
whether it worked.

**Common violations**:
- Tests that only `print`/`console.log` a value for a human to eyeball.
- Tests with no assertions at all (they "pass" only because nothing threw).
- Overly loose assertions that would pass regardless of correctness (e.g.,
  asserting a value is "truthy" when a specific value is expected).
- Swallowing exceptions so a real failure gets silently ignored.

**Concrete check**: Every test must contain at least one assertion that checks
a specific, meaningful expected value (return value, thrown error type/message,
state change, or call arguments) — not just "did it run without throwing."
Run the test once against the buggy/pre-fix behavior (or temporarily invert the
assertion) to confirm it actually fails when the code is wrong, then confirm it
passes against the fixed code.

## T — Timely

**What it means**: Tests for a change are written and run as part of the change
itself — right after (or alongside) the code they cover — not deferred to some
later cleanup pass that may never happen.

**Common violations**:
- Shipping the fix now and leaving a `// TODO: add tests` for later.
- Writing tests for old, unrelated code instead of the code that just changed,
  as a substitute for testing the actual change.
- Writing tests so long after the fix that they test today's behavior rather
  than the specific regression/bug being guarded against.

**Concrete check**: A test must exist for each new/changed function or branch
introduced by the fix before that unit of work is considered complete, and it
must be runnable in the current state of the repository (not blocked on future
work). Scope tests to the diff at hand — do not defer, and do not expand into
an unrelated full-suite rewrite.

## Final self-review checklist

Before considering a generated test (or test file) done, confirm all of the
following:

- [ ] **Fast** — no real network/disk/DB/server calls, no sleeps; runs in
      milliseconds.
- [ ] **Independent** — passes alone and in any run order; no shared mutable
      state leaks in or out; fresh fixtures per test.
- [ ] **Repeatable** — no reliance on real time, randomness, unordered
      iteration, or environment; any such source is pinned/mocked/seeded.
- [ ] **Self-validating** — contains specific assertions on expected
      values/errors; verified to fail against the old/buggy behavior and pass
      against the fixed behavior; no bare `print`/log-only checks.
- [ ] **Timely** — covers the actual changed function(s)/branch(es) from this
      fix, scoped to the diff, not a deferred TODO or an unrelated rewrite.

If any box can't be checked, fix the test before reporting it as complete.
