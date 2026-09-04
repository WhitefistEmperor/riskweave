# Phase 5C production hardening

Baseline `b552cb7ac29bbed93ea4398e8ebe22919d9ac389`, branch `phase5b-frontend-v2`.
No public/staging deployment. Detector, generator, graph, evidence and benchmark are out of scope.

## Authentication and security milestone

Production supports `auth_mode=jwt`: offline RS256 verification with PyJWT/cryptography and an
operator-provisioned public JWKS file. Issuer, audience, required scope, expiration, not-before,
issued-at and subject are checked. Default maximum token lifetime is 900 seconds. Algorithms are
fixed; token key URLs are never fetched. Unknown keys fail closed. Rotation: provision overlapping
public keys, restart the single backend, wait out the old token lifetime, remove the old key/restart.
Identity is a deterministic hash of the verified issuer/subject pair, not a client ID or email.
Missing/invalid credentials return 401; valid credentials without the analyst scope return 403;
cross-owner objects retain non-disclosing 404. Development headers only work in development/test.
`disabled` denies all protected routes; missing/invalid JWT configuration prevents startup.

The minimal adapter is not an identity provider or a browser login implementation. Before staging,
configure a maintained OIDC gateway with an application-specific audience/scope and short-lived
access tokens. The gateway authenticates every UI/API request and forwards the user's access token
to `/api` as Authorization. Prefer routing `/api` directly to the private backend. Strip incoming
identity/forwarded headers and never use a shared service token for all analysts. Protect backend
and frontend origins from direct access. Terminate TLS at this gateway; private-hop encryption or
an isolated trusted network is required. Restrict proxy-header trust to the gateway IP, never `*`.
The browser stores no API tokens. Gateway session cookies must be Secure, HttpOnly, SameSite=Lax
or Strict, narrowly scoped, short-lived; gateway login/logout/CSRF protection must be verified on
the chosen deployment. API cookies are not accepted as authentication, and disallowed Origin
requests are rejected before mutation. The adapter does not provide immediate JWT revocation;
expiry bounds the revocation window. No live identity-provider integration has been claimed.

Session response is an explicit additive contract extension: `authentication_mode` now accepts
`jwt` and `production_authentication` may be true. The frontend validates the matched pair and
shows a verified-session label. No UI redesign. Existing development contract remains identical.

API: explicit trusted Host and Origin checks, bounded bearer input, no-store responses, request
IDs, nosniff, DENY framing, no-referrer, restrictive API CSP, permissions policy, production HSTS;
production interactive docs disabled. Preflight rejection retains the existing 400 contract.
Frontend: nosniff/frame/permissions/referrer headers and frame/object/base CSP restrictions.
This is not a nonce-based script CSP: Vinext inline hydration requires separate tested integration.
Production proxy target must be explicit and credential-free; browser API requests stay same-origin.
Gateway must repeat security headers on its own errors and enforce TLS/body/header/rate limits.

Implementation references: [PyJWT verification](https://pyjwt.readthedocs.io/en/stable/usage.html)
and [OWASP REST security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html).

## Operational limits and process safety

One API worker/replica and one local analysis child are supported. The scheduler acquires a
PostgreSQL session advisory lock (or a SQLite adjacent OS lock) plus a storage-root OS lock before
recovery. Another scheduler fails startup. A separate analysis lock prevents startup recovery while
an orphan child is still working. Children have a final watchdog (configured timeout + 5 seconds);
normal timeout/shutdown still kills and waits from the parent. Stale lock files are harmless and
must not be deleted to bypass ownership. Local disk only; NFS/SMB and multi-host topology unsupported.
Lost PostgreSQL lease sessions stop the scheduler; readiness fails when its thread exits. Database
operations use bounded connect/statement/lock timeouts. No automatic retry of interrupted runs.

Limits default to 1,000 investigations/owner, 10,000 total, 20 artifacts/investigation,
50 runs/investigation, 100 globally pending runs, 2 GB object storage, 100 MB per serialized result,
and the existing 25 MB upload limit. Quota admission is serialized in SQL; duplicate inputs and
idempotent run repeats are checked before quotas. Storage byte admission uses a cross-process OS
lock and includes orphan JSON objects. Quota errors use a documented new safe 429 `QUOTA_EXCEEDED`;
storage-lock contention uses 409, permitting deliberate retry. No data is automatically deleted.
The 90-day retention setting is a review policy, not an erasure promise. OS/disk quotas, gateway
rate/concurrency limits and a finite log rotation policy remain operator responsibilities.

## Verification log

- Final frontend suite against the rebuilt production-configured frontend and restarted hardened
  backend: **27 passed**, 2.7 minutes (22 browser/E2E, 5 non-browser checks). TypeScript and lint passed.
  Fresh/repeated migration CLI checks passed. Frozen checksum remains unchanged. No public deployment.

- Final Python suite after all worker fixes: **94 passed**, 2 existing dependency deprecation
  warnings, 86.31 seconds. Ruff passed. Final wheel/sdist rebuilt; process/backup modules,
  original migrations and packaged frozen benchmark verified.
- Real optional-LLM-disabled smoke: readiness `ready`; persisted-ring investigation returned
  `disabled_evidence_only` and six computed, cited statements without a paid call. Running the
  original browser suite in this alternate mode exposed its intentionally mode-specific expected
  fallback label (it expects deterministic mode, not the disabled-mode label). That run was stopped;
  final full browser regression uses the original deterministic configuration. Neither mode's UI
  label or existing assertion was weakened to hide this configuration mismatch.
- Final frontend config validation also rejects malformed proxy values with a generic startup
  error, avoiding accidental credential disclosure in URL parser errors. A separate Node-process
  test verifies missing/malformed/credential-bearing targets fail and an explicit valid origin passes.

- Extended process/auth/PostgreSQL-contract milestone: **30 tests passed**, Ruff passed, including
  actual cross-process lock exclusion and lock release after Windows process-tree termination.

- Full regression first pass: 91 Python tests passed. Two subsequent additional test-fixture issues
  were investigated: the JWT library rejects a null issuer at signing time, so missing-claim tests
  now actually omit the claim; and a real Windows subprocess test found that killing a venv launcher
  alone can leave its Python child holding a lock. The executor now terminates its owned process
  tree (`taskkill /PID <owned pid> /T /F` on Windows; a dedicated process group on POSIX).
  No image-name/global process kill is used. Parent-death watchdog/analysis lock remain defense in depth.
  The existing subprocess observation test now filters for the actual analysis command, so its
  unchanged exit assertions do not accidentally inspect the successful `taskkill` helper instead.
  See [Microsoft process-tree termination](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/taskkill).
- Browser full-suite first run: 25 passed, one local generator failed because the sandbox denied
  uv cache access. No assertion was weakened. Authorized rerun: **26 passed**, including the original
  24 plus two new session/security tests. All UI widths and the real upload/analysis/revisit passed.
- Python wheel and sdist built; packaged backup module, original migration and frozen benchmark
  checksum verified. Compose YAML structural/loopback/capability-drop checks passed, explicitly
  not equivalent to `docker compose config` or actual image execution.

- Backup/observability milestone: 15 backup and security tests passed. Real SQLite restore into
  new targets preserved result hashes, ownership and migration state. PostgreSQL tools unavailable.
- Structured startup log contains environment, auth mode, database dialect, worker topology,
  optional provider mode and limits, never configuration values containing credentials/paths.
  Analysis completion logs now include actual status and duration. HTTP request IDs remain intact.
  Backup procedure and consistency caveats are in `docs/backup-restore.md`.

- Operational milestone: 20 quota/lifecycle/API tests passed, including real subprocess completion,
  timeout, worker failure, graceful shutdown and restart. Ruff passed.

- Before edits: 20 baseline API/persistence/provider tests passed, 2 upstream warnings.
- Initial sandbox Python/cache access failed; authorized installed-runtime execution succeeded.
- First dependency sync was interrupted by the prior running API executable's Windows file lock.
  Stopped that local preview without touching its data; locked sync then completed.
- Auth/security first run: 29 passed, one existing preflight status regression. Restored its 400
  contract rather than changing the assertion. Existing production test now uses its configured
  trusted HTTPS hostname, retaining all assertions.
- Frontend TypeScript, lint and production build passed after security/session changes.
- Final auth/security milestone: 30 tests passed; Ruff and whitespace checks passed.
- Fresh Python audit including the new JWT/crypto dependencies: no known vulnerabilities;
  local unpublished RingSentinel skipped, audit-tool overlay dependencies included.
- Fresh npm audit succeeded: zero affected packages across the full 702-package reported tree.
  Initial sandbox advisory request failed; authorized official-registry retry succeeded.
