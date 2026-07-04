# Security Report: 001-task-api-defects

## Summary

Two source files were reviewed (`src/task_tracker_api/main.py` and
`src/task_tracker_api/store.py`). The intended security fix for Issue 3 was
implemented correctly in its two core aspects: the hardcoded literal
`"supersecret-admin-key-123"` is gone, and the credential comparison now uses
the timing-safe `hmac.compare_digest` instead of plain `==`. However, the fix
introduces a fail-open weakness: the admin key falls back to a well-known,
source-committed default (`"dev-local-admin-key-000"`), so a deployment that
forgets to set `ADMIN_API_KEY` silently protects the destructive
`DELETE /admin/tasks` endpoint with a publicly-known credential. Highest
severity present: MEDIUM. Overall verdict: CHANGES REQUESTED — the core
hardening is sound, but the default-credential behavior should be addressed
before this is relied on outside local development.

## Scope Reviewed

- Bug case directory: `/Users/yuriihabrusiev/Developer/yuriihabrusiev/gen-ai-software-engineering/homework-4/context/bugs/001-task-api-defects`
- Files reviewed (from fix-summary.md):
  - `/Users/yuriihabrusiev/Developer/yuriihabrusiev/gen-ai-software-engineering/homework-4/src/task_tracker_api/main.py`
  - `/Users/yuriihabrusiev/Developer/yuriihabrusiev/gen-ai-software-engineering/homework-4/src/task_tracker_api/store.py`
  - Supporting context read (not changed by this fix): `src/task_tracker_api/models.py`, `mise.toml`

## Findings

### Injection

No injection vulnerabilities found in the reviewed files. The data layer in
`store.py` operates entirely on an in-memory `dict` (`tasks`) using native
dictionary access and comprehensions; there is no SQL, shell/`exec`, template
rendering, LDAP/XPath, or other interpreter reached by user input. The
`sort == "priority"` branch compares against a fixed string literal and looks
up a static `_PRIORITY_ORDER` map keyed by a validated `Priority` enum, so the
sort key cannot be influenced by arbitrary input.

### Hardcoded Secrets/Credentials

- **Severity:** MEDIUM
  **Location:** `src/task_tracker_api/main.py:23` (used at `src/task_tracker_api/main.py:66`)
  **Description:** `ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "dev-local-admin-key-000")`
  removes the previous hardcoded secret but replaces it with a fail-open
  default. If the `ADMIN_API_KEY` environment variable is not set (e.g. a
  production/staging deploy that never runs under `mise`), the application
  starts anyway and gates the destructive `DELETE /admin/tasks` bulk-delete
  endpoint behind the string `"dev-local-admin-key-000"`. That value is
  committed in both this source file and `mise.toml`, so it is publicly known
  to anyone with repository access. The result is that a misconfigured
  deployment exposes an authenticated-by-a-known-key data-wipe operation,
  effectively unauthenticated destructive access. This is an authentication
  weakness contingent on deployment misconfiguration rather than a
  directly-exploitable leak, hence MEDIUM rather than HIGH; the impact is data
  loss (all tasks cleared) on an in-memory demo store.
  **Remediation:** Prefer fail-closed behavior for the admin credential.
  Options (describe only, do not apply): read the key with
  `os.environ["ADMIN_API_KEY"]` and fail startup (or disable the admin route)
  when it is unset outside an explicit local-dev mode; or keep a default only
  when an explicit `ENV`/`APP_ENV` flag indicates local development and refuse
  to boot with the dev default in any non-dev environment; and add a startup
  assertion that the effective key is not equal to the shipped dev default when
  running in a deployed environment.

### Insecure Comparisons

No insecure comparisons found. The fix correctly replaced the previous
`x_admin_key == ADMIN_API_KEY` (short-circuiting, timing-observable) with
`hmac.compare_digest(x_admin_key, ADMIN_API_KEY)` at
`src/task_tracker_api/main.py:66`, which is the appropriate constant-time
comparison for a shared-secret credential. The remaining `==` uses in the
reviewed code (`task.completed == completed` in `store.py:29`) compare
non-secret boolean/business data and are appropriate.

### Missing Input Validation

- **Severity:** LOW
  **Location:** `src/task_tracker_api/main.py:65-66`
  **Description:** `x_admin_key: str = Header(...)` accepts an arbitrary
  client-supplied header value, which is passed directly to
  `hmac.compare_digest`. When called with two `str` arguments,
  `hmac.compare_digest` requires both to be ASCII-only and raises `TypeError`
  on non-ASCII input. A request sending a non-ASCII `X-Admin-Key` header would
  therefore trigger an unhandled exception surfacing as an HTTP 500 rather than
  the intended 403, allowing an attacker to distinguish "bad key" (403) from
  "non-ASCII key" (500) and to trigger error paths at will. Impact is low
  (minor behavioral/info-leak and error-noise), but it is a validation gap on
  attacker-controlled input.
  **Remediation:** Normalize/encode the header before comparison — e.g. compare
  `x_admin_key.encode("utf-8")` against `ADMIN_API_KEY.encode("utf-8")` so
  `compare_digest` operates on bytes (which tolerates any byte value), and/or
  wrap the comparison so any exception maps to a 403 rather than a 500. Do not
  apply here; describe only.

Other inputs are adequately validated: `task_id: int` is coerced/validated by
FastAPI's path handling (`main.py:41,49,57`), and the request body is validated
by the Pydantic `TaskCreate` model (`models.py`), including `title` with
`Field(min_length=1)` and `priority` constrained to the `Priority` enum. No
issues found there.

### Unsafe/Vulnerable Dependencies

No dependency manifests were touched by this change. The fix modified only
`main.py` and `store.py`; `pyproject.toml`, `uv.lock`, and other manifests are
outside the scope of this fix and were not altered. The only new imports added
(`hmac`, `os`) are Python standard library modules with no supply-chain
exposure. No action required for this category.

### XSS/CSRF

Not applicable / none found. The reviewed code is a JSON API that returns
Pydantic models and static error details (`"Task not found"`, `"Forbidden"`);
there is no HTML/JS templating or unescaped rendering of user input, so XSS
does not apply. For CSRF: the sole reviewed state-changing sensitive endpoint
(`DELETE /admin/tasks`) authenticates via a custom `X-Admin-Key` request
header rather than an ambient cookie/session. Browser-driven cross-site
requests cannot set arbitrary custom headers under CORS, and the app defines no
cookie-based authentication, so classic CSRF is not exploitable against this
change. No CSRF finding.

## Overall Recommendation

CHANGES REQUESTED — the intended hardening (removal of the hardcoded secret and
switch to `hmac.compare_digest`) is correct, but the MEDIUM fail-open default
credential means the destructive admin endpoint can be protected by a
publicly-known key in any deployment that does not set `ADMIN_API_KEY`; adopt
fail-closed handling before relying on this outside local development.
