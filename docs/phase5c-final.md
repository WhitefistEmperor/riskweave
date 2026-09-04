# Phase 5C final verification report

Date: 2026-09-04. Baseline: `b552cb7ac29bbed93ea4398e8ebe22919d9ac389`.
Branch: `phase5b-frontend-v2`.

Phase 5C implements the local hardening foundation. **It is not approval for staging or public
production.** Unavailable container/PostgreSQL and real identity-gateway gates remain explicit.
No deployment or Phase 5D work was performed.

## Authentication and security

The new minimal adapter verifies RS256 access tokens using PyJWT/cryptography and an operator-pinned
public JWKS file. It requires a configured HTTPS issuer, dedicated audience, analyst scope, subject,
issued-at/not-before/expiry, and at most 900 seconds of token lifetime by default. No algorithm
negotiation or token-provided key URL fetch occurs. Identity derives only from verified issuer/subject.
Missing/invalid credentials return 401; missing analyst scope returns 403; cross-owner resources stay
non-disclosing 404. Client identity headers cannot override authenticated ownership. Development
mode remains distinct; disabled mode denies protected access; invalid JWT configuration stops startup.

Production browser login is delegated to a maintained OIDC gateway, **not implemented or live-tested
here**. It must protect UI/API, issue short-lived scoped tokens, forward each user's access token,
secure its own session cookies/logout/CSRF flow and block direct backend/frontend access. RingSentinel
stores no bearer tokens in browser storage and does not authenticate cookies. Immediate JWT
revocation is not implemented; expiry and operator key rotation bound the window.

HTTP protection includes explicit Host/Origin checks, CORS, no-store API responses, request IDs,
nosniff, frame denial, no-referrer, permissions policy and production HSTS. API CSP is restrictive;
frontend CSP restricts framing, objects and base URLs but is **not a nonce-based script CSP**.
Production API docs are disabled. Frontend production proxy settings must be explicit, same-origin
for browser requests, and credential-free; malformed URL errors are sanitized. Existing upload/path
validation and safe errors remain. The session auth-mode union and quota 429 category are explicit
contract additions, not silent changes. Only necessary session-label/header/configuration UI changes
were made; the Sites skill guided preservation of the existing frontend and local verification.

## Operational controls

| Control | Default / behavior |
|---|---|
| Upload | 25,000,000 bytes, existing streaming enforcement retained |
| Investigations | 1,000 per owner; 10,000 total |
| Artifacts / runs | 20 artifacts and 50 runs per investigation |
| Pending queue | 100 globally queued/running runs |
| Object storage | 2,000,000,000 bytes, including orphan JSON objects |
| One result | 100,000,000 serialized bytes |
| Analysis | 300-second parent timeout; orphan watchdog at timeout + 5 seconds |
| Retention | 90-day read-only review policy; no automatic deletion |

All limits are environment-driven. SQL admission is serialized; byte-identical uploads and repeated
idempotency keys are resolved before quota rejection. Storage writes have cross-process byte-budget
admission. No existing data was deleted. Gateway rate/concurrency limits, disk quotas, log rotation
and a reviewed retention/legal-hold policy remain operational responsibilities.

Exactly one API/executor replica on one host with local disk is supported. SQLite OS locks or a
PostgreSQL session advisory lock prevent duplicate executors; storage and analysis locks protect
restart recovery. Lost lease sessions stop scheduling. Queued work survives restart; interrupted
work becomes failed rather than automatically re-executed. Graceful shutdown/timeout terminate the
owned child tree. An added real test exposed Windows venv launcher orphaning; termination now
targets its process tree, with POSIX isolated process-group handling. No distributed queue or GNN.

Structured startup/request/analysis logs include request IDs, safe categories, actual status,
duration and an allowlisted non-secret configuration summary. Health/readiness include database,
storage and executor availability. Optional provider availability does not gate readiness.

## Backup and restore

Offline tool: `python -m ringsentinel.platform.backup`. It snapshots the database plus object files,
writes a checksummed completion manifest, validates references and restores objects before metadata
into **new** targets only. Standard pg_dump/pg_restore paths and SQLite backup are supported.
Real SQLite round-trip tests preserved ownership, results, checksums and migration state. Corruption,
traversal, overwrite and active-executor cases are rejected. No automatic deletion or live cutover.

All writers must be stopped: the acknowledgement flag and locks are not a universal traffic-draining
system. PostgreSQL snapshots alone are not atomic with filesystem writes. Backups need separately
managed encryption/access control, configuration/secrets backups, retention and RPO/RTO decisions.
Live PostgreSQL restore is **unverified**. See `docs/backup-restore.md` for exact steps.

## Measured checks

| Check | Actual result |
|---|---|
| Full Python suite | **94 passed**, 2 existing dependency warnings, 86.31 seconds |
| Ruff | Passed |
| Frontend full suite | **27 passed**, 2.7 minutes; 22 browser/E2E + 5 non-browser checks; original 24 retained |
| TypeScript / frontend lint | Passed |
| Production frontend build | Passed, including explicit production environment/proxy configuration |
| Python wheel / sdist | Built; process/backup modules, original migration and frozen benchmark verified |
| Migration CLI | Fresh SQLite upgrade and repeated upgrade passed |
| PostgreSQL compatibility | Actual migration/ORM SQL compiled; backup command contracts passed, no live server |
| Backup restore | Real throwaway SQLite/input/result restoration passed |
| Optional LLM disabled | Actual ready API and six computed investigator statements; no paid call |
| npm audit | **0 affected packages**, full reported 702-dependency tree |
| pip-audit | No known third-party vulnerabilities; unpublished local package skipped |
| Compose | Structural YAML/loopback/capability-drop checks passed, not runtime validation |
| Docker/PostgreSQL runtime | Not run: Docker, Podman, psql, pg_dump and pg_restore absent |

Only PyJWT and its cryptographic dependency closure were added; existing locked dependencies were
not broadly upgraded. Frontend dependency files are unchanged. Zero package advisories do not imply
penetration-test, supply-chain or image-scan approval.

Earlier failures are retained in `docs/phase5c-hardening.md`: sandbox cache access, restored preflight
400 contract, an additional test fixture's null-vs-missing issuer, the genuine Windows child-tree
issue, and a mode-specific browser-label mismatch when testing disabled instead of deterministic
LLM mode. Existing assertions were retained; the Windows process observer now distinguishes the
analysis subprocess from its termination helper. No failure was relabeled as a pass.

## Benchmark integrity

Protected detector/graph/features/models/generator/evidence/benchmark/replay runtime and analysis
adapter paths are unchanged from Phase 5B. Benchmarks were not regenerated. Repository and packaged
Phase 3 SHA-256 both match:

`42c0234331f2b467ccc296f6579478d2feaf7c71e9c159387b6674a09b27e976`

## Unresolved production risks / next authorized gates

- Real gateway/provider token issuance, cookie/session/logout/CSRF, TLS and private-origin routing
  have not been integrated or tested against a live identity provider. Key rotation and revocation
  operations need rehearsal; legacy development identities are not automatically migrated.
- No Docker image build, Compose runtime, live PostgreSQL migrations/concurrency/lease/restore,
  container restart or Linux execution. Exact remaining commands are in
  `docs/phase5c-container-verification.md`. Remote CI was not run.
- Vinext remains beta with known cancelled-stream log noise and build notices. No full script CSP,
  base-image digest pinning, SBOM/image scan, broad penetration test or production load test.
- Single-host/local-disk/single-worker only; no HA, fairness or distributed exactly-once guarantee.
  Local storage and SQL are not one atomic transaction; crash-orphan objects consume quota.
- Gateway rate/connection/body limits, encryption at rest, backup scheduling/encryption/restore drills,
  monitoring alerts and legally appropriate deletion/privacy controls need deployment-specific work.
- Optional paid provider was not live-tested. Existing bounded timeout/retry/fallback tests pass;
  timeouts are per attempt, not an overall wall-clock deadline. Computed evidence remains authoritative.
- Synthetic-trained, uncalibrated detector and DatasetBundle-only ingestion remain explicit product
  limitations; no real-payment validation or production fraud-performance claim is made.

## Checkpoints

| Milestone | Commit |
|---|---|
| Authentication / HTTP security | `011995a` |
| Quotas / executor ownership | `0187833` |
| Backup / observability | `eb932c7` |
| Process-tree fix / audits / verification gates | `64c70fc` |
| Final checks / documentation | Commit containing this report |

Only source, tests, dependency lock, configuration templates and documentation belong in these
commits. Local datasets, databases, snapshots, screenshots, caches and builds remain ignored.
Final full commit hash and working-tree status are recorded in the delivered report after commit.
