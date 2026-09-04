# Phase 5A: persisted investigation foundation

This is an architecture foundation, not a public-production deployment. The Phase 4 analyst demo
remains available. Phase 5A adds persisted investigations and stable application boundaries without
changing the validated detector, synthetic generator, feature semantics, thresholds, or benchmark.
No GNN, frontend redesign, public hosting, or live authentication provider is introduced.

Actual checks and limitations are recorded in [the verification log](phase5a-verification.md).
Container recipes and CI configuration are not evidence that either has executed successfully.
See the separate [dependency audit](dependency-audit.md) and
[container verification record](container-verification.md) for those scopes.

## 1. Current architecture

```text
Browser: existing demo + minimal persisted-investigation routes
  -> centralized typed HTTP client
  -> FastAPI /api/v1 + owner-scoped application service
       -> SQLAlchemy metadata / explicit Alembic migrations
       -> StorageBackend for input and immutable result objects
       -> database queue -> one scheduler -> one killable analysis subprocess
            -> unchanged Phase 3 model adapter -> computed evidence -> persisted result
  -> optional investigator selects only facts from that persisted evidence
```

The unversioned `/api/...` surface remains a separate synthetic-demo compatibility API. Its replay
continues to use observed-prefix snapshots. New product clients should use `/api/v1/...`; they must
not treat the demo runtime as the store for an uploaded investigation.

`api/contracts.py` owns public Pydantic schemas, `api/platform_api.py` owns HTTP adaptation,
`platform/service.py` owns authorization and transactions, and `platform/jobs.py` owns scheduling.
`platform/analysis.py` is a narrow adapter, not a new detection algorithm.

## 2. Domain model

| Record | Ownership and purpose | Important metadata |
|---|---|---|
| User | Principal identity; no invented profile data | ID, created/updated UTC timestamps |
| Investigation | Belongs to one User; groups inputs and runs | Name, constrained status, source/analysis metadata |
| Artifact | Belongs to one Investigation; input reference | Original display name, opaque key, MIME type, byte count, SHA-256 |
| AnalysisRun | Belongs to one Investigation and one input Artifact | Status, idempotency key, start/end times, safe failure, versions, configuration, result reference/checksum |

An investigation may have several inputs and historical runs. A completed result belongs to its run;
starting another run does not overwrite it. The same candidate ID in two runs is not a globally unique
finding: use `(run_id, candidate_id)` as the UI/query scope.

The shared status vocabulary is `created`, `uploading`, `queued`, `running`, `completed`, and `failed`.
Runs normally use only the last four. `uploading` is a transactional investigation lock, not a promise
of observable upload-progress events. Investigation status summarizes current activity; historical
run status remains independently queryable.

## 3. Database and migrations

SQLAlchemy provides portable relational mappings; Alembic migration `0001` explicitly creates the
schema. Foreign keys, owner/investigation/run lookup indexes, unique input checksums per investigation,
and run idempotency constraints are applied by migrations. SQLite connections enable foreign keys.
UTC timestamps are normalized in API responses, including SQLite's timezone-naive return values.

The default development URL is `sqlite:///./work/ringsentinel.db`. PostgreSQL uses the installed
psycopg driver, for example `postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE`, supplied through
`RINGSENTINEL_DATABASE_URL`. Credentials are never committed. SQLite is the locally exercised database;
PostgreSQL compatibility is an architectural target and a Compose recipe, not a claimed live-server
verification unless recorded in the verification log.

Run from the repository root before API startup:

```text
uv sync --locked --extra dev
uv run ringsentinel-migrate
uv run ringsentinel-api
```

The migration command can be repeated. The application never calls `create_all()` or upgrades the
schema on startup. A missing/unmigrated database leaves readiness unavailable; migrate and then
restart the API so the scheduler starts. The default command creates the local `work/` directory;
operators using a different SQLite parent must provision it and its permissions.

Transactions combine owner checks, state transitions, and metadata writes. There is deliberately no
distributed transaction between the database and object storage; see the durability limitations below.

## 4. Storage and upload boundary

`StorageBackend` exposes `save`, `read`, `exists`, `delete`, `reference`, and `ready`. Its local
implementation stores objects under `RINGSENTINEL_STORAGE_ROOT`, default `work/storage`. Object keys
are generated opaque UUID-hex names, not user filenames. Keys must match the allowlisted shape;
traversal, absolute paths, and symlink escapes are rejected. Exclusive creation never overwrites an
existing object. Failed writes and rolled-back metadata changes attempt to remove only newly created
objects. Public response schemas exclude storage keys and local paths.

Uploads are raw `application/json` bodies containing a complete `DatasetBundle`, not multipart data,
arbitrary CSV, or a single exported JSONL table. The API authorizes before consuming the body, rejects
unsupported content types and path-like display filenames, and enforces the size limit while reading
chunks, independently of `Content-Length`. The default limit is 25,000,000 bytes. Schema and
cross-record validation reject malformed bundles, empty event collections, and inconsistent references.
This input contract still includes synthetic label/ground-truth tables; they are validated as input
metadata, never used to train or score the uploaded events. General unlabeled payment ingestion is not
implemented in this phase.

Input bytes are SHA-256 checked in the worker. Re-uploading byte-identical content into the same
investigation reuses the input Artifact when the investigation is idle. Semantically equal JSON with
different bytes is not deduplicated. Results are canonical JSON objects saved once, referenced from
the completed run, and checksum-checked on read. Results contain candidates and all computed evidence
queries; they are not re-inferred on each browser request. The relational record supplies the owning
investigation/run association rather than duplicating large evidence tables in SQL.

## 5. Versioned API contracts

The running API exposes OpenAPI at `/openapi.json` and interactive documentation at `/docs`.
Requests reject unknown schema fields; responses provide stable IDs, explicit statuses, ISO UTC
timestamps, and typed evidence. The `/api/v1` prefix applies to all routes below.

| Method and route | Contract |
|---|---|
| `GET /health` | Cheap process liveness and application version |
| `GET /ready` | Migration/domain-table access and storage read/write check; 503 if unavailable |
| `GET /session` | Current development principal and explicit non-production-auth flag |
| `GET/POST /investigations` | Owner-scoped list / create with `{ "name": "Review" }`; create returns 201 |
| `GET /investigations/{id}` | Owned investigation, otherwise 404 |
| `GET/POST /investigations/{id}/artifacts` | List / raw DatasetBundle JSON upload; optional `X-Filename`; upload returns 201 |
| `GET/POST /investigations/{id}/runs` | List / enqueue `{ "artifact_id": "..." }` with `Idempotency-Key`; enqueue returns 202 |
| `GET /runs/{id}` | Poll persisted state and safe failure details |
| `GET /runs/{id}/results` | Full persisted result; 409 until completed |
| `GET /runs/{id}/rings` | Candidate summaries for this run |
| `GET /runs/{id}/rings/{candidate_id}` | One candidate scoped to the owned run |
| `GET /runs/{id}/rings/{candidate_id}/evidence` | All authoritative evidence-query outputs |
| `POST /runs/{id}/rings/{candidate_id}/investigate` | Grounded explanation for `{ "question": "..." }` |

The evidence object contains `get_candidate_ring`, `get_ring_members`, `get_shared_devices`,
`get_shared_ips`, `get_shared_cards`, `get_shared_addresses`, `get_shared_payout_accounts`,
`get_transaction_timeline`, `get_refund_patterns`, `get_merchant_relationships`, `get_temporal_activity`,
`calculate_exposure`, and `compare_member_behavior`. Empty collections are valid; a completed run with
no candidates is not a failed analysis. Money remains in integer minor units. Scores are uncalibrated
synthetic-model outputs, not probabilities of financial loss.

## 6. Authentication and ownership

`current_principal` is the replaceable identity boundary. In development/test mode only,
`X-Development-User` selects an allowlisted local identity; omission uses `local-analyst` unless
configured otherwise. This header is **not authentication**: anyone who can reach the local service can
select another development identity. It exists to exercise owner scoping, not to protect public data.

Every investigation/run/input/result/evidence operation passes through owner-scoped service access.
Another principal receives 404 for guessed IDs; the response does not disclose the resource's existence.
Future authenticated principals must enter through this same boundary, not bypass service authorization.

Production settings reject development authentication and the demo surface. With the currently
available `auth_mode=disabled`, protected product routes fail closed with 401; this does not mean
anonymous access. A real session/OIDC adapter is required before a useful public deployment. Health
and readiness do not need a principal. Local demo routes are not private investigation resources and
are disabled in production mode.

## 7. Analysis lifecycle and execution limits

Run creation persists `queued` and returns without running the model in the HTTP handler. A single
scheduler polls the database approximately every 250 ms, atomically claims one queued run, marks it
`running`, then starts `python -m ringsentinel.platform.worker RUN_ID` without a shell. The child reads
and validates the stored input checksum, uses the unchanged Phase 3 adapter, persists the computed
result, and completes the run. The API remains available for polling during the CPU-heavy work.

There is one active child at a time across this API process. The default analysis timeout is 300 seconds;
the parent kills and waits for an over-time child before recording `ANALYSIS_TIMEOUT`. Controlled
shutdown interrupts the child with `WORKER_INTERRUPTED`; unexpected worker exit becomes
`ANALYSIS_FAILED`. A restart marks persisted running work interrupted and leaves queued work eligible.
Interrupted jobs are not automatically retried. A user may request a new run with a new idempotency key.

A unique nullable active slot and conditional investigation transition allow at most one queued/running
run per investigation. Repeating an existing `(investigation, idempotency key, artifact)` returns the
existing run; reusing a key for a different artifact conflicts. Different keys cannot start concurrent
active runs. Simultaneous conflicting requests may receive 409; clients should refetch rather than
silently inventing a new key. Polling never replays the enqueue POST.

This is a local database queue, **not distributed execution or an exactly-once guarantee**. Run exactly
one API worker/replica with this executor. There is no lease, heartbeat, multi-host coordination,
per-user fairness, queue quota, automatic retry policy, or task cancellation API. A future queue adapter
can retain the enqueue/poll/results contracts but must implement those guarantees explicitly.

## 8. Safe errors, request IDs, and observability

All API requests receive a server-generated `X-Request-ID`. Safe errors consistently return:

```json
{"error":{"code":"NOT_FOUND","message":"Resource not found.","request_id":"..."}}
```

Categories include validation (422), unauthorized (401), forbidden (403), not found (404), conflict
(409), upload too large (413), invalid dataset (422), analysis failed (500), timeout (504), interrupted
worker/provider/readiness unavailable (503), and internal error (500). A failed run is normally read as
a successful status response containing its safe failure code; it is not a failed polling transport.
Invalid preflight requests use a safe 400 envelope; unsupported methods use 405.

Structured HTTP logs capture request ID, method, matched route template, status, duration, and failure
category, plus validated investigation/run IDs when present. Worker logs identify run completion/failure.
Raw paths, uploaded content, evidence, authorization headers, keys, and raw exception messages are not
logged by these application boundaries. Frontend errors carry the response request ID for correlation.
Reverse-proxy/platform logging must preserve this privacy boundary when added later.

## 9. Configuration

Settings are loaded from environment variables; `.env.example` is a template, not automatically loaded
by Python. Set variables in the launching shell or a secret-capable runtime. Database credentials and
the optional OpenAI key use secret-valued settings and are not response fields.

| Variable | Default / purpose |
|---|---|
| `RINGSENTINEL_ENVIRONMENT` | `development`; also `test`, `production` |
| `RINGSENTINEL_DATABASE_URL` | Local SQLite URL; PostgreSQL+psycopg supported by adapter |
| `RINGSENTINEL_STORAGE_ROOT` | `work/storage` |
| `RINGSENTINEL_AUTH_MODE` | `development`; `disabled` denies protected access |
| `RINGSENTINEL_DEVELOPMENT_USER_ID` | `local-analyst`, used only in development/test |
| `RINGSENTINEL_FRONTEND_ORIGINS` | JSON array of explicit localhost origins; no wildcard |
| `RINGSENTINEL_API_HOST`, `RINGSENTINEL_API_PORT` | `127.0.0.1`, `8000` for the local launcher |
| `RINGSENTINEL_LOG_LEVEL` | `INFO` |
| `RINGSENTINEL_DEMO_ENABLED`, `RINGSENTINEL_JOBS_ENABLED` | Both `true`; disable jobs only for controlled checks/operations |
| `RINGSENTINEL_UPLOAD_LIMIT_BYTES` | `25000000` |
| `RINGSENTINEL_ANALYSIS_TIMEOUT_SECONDS` | `300`, bounded 1–3600 |
| `RINGSENTINEL_LLM_PROVIDER` | `deterministic`; also `disabled`, `openai` |
| `RINGSENTINEL_OPENAI_MODEL` | `gpt-5.4-mini`; used only for configured optional provider |
| `OPENAI_API_KEY` | Optional server-side secret, never needed for startup |
| `RINGSENTINEL_LLM_TIMEOUT_SECONDS` | `20`, positive and at most 60 per request |
| `RINGSENTINEL_LLM_RETRY_COUNT` | `0`, bounded 0–2 |
| `RINGSENTINEL_LLM_MAX_OUTPUT_TOKENS` | `1200`, bounded 100–4000 |
| `RINGSENTINEL_BUILD_COMMIT` | `unknown` unless supplied; safe Git SHA value |
| `NEXT_PUBLIC_RINGSENTINEL_API_BASE_URL` | Build-time; empty for same-origin requests, otherwise API origin without `/api` |
| `RINGSENTINEL_API_PROXY_TARGET` | Frontend server-side proxy target; set at build and startup; local backend by default |

Production requires explicit HTTPS CORS origins and rejects wildcard/development identity settings.
CORS is a browser policy, not authorization. Optional LLM availability is not part of readiness.
`jobs_enabled=false` allows inspection without execution; queued jobs will not complete until an
executor starts. Configure and migrate before starting the process.

Each run records application version, `phase3-network-hgb` detector identifier, optional build commit,
result/configuration schema versions, input checksum, training/validation seeds, and timeout snapshot.
The frozen fold uses training seeds 102/103/104, validation seed 101, and model random state 105 with
5,000 payments per training ecosystem. Uploaded ground truth does not enter model fitting. This is
traceability of a synthetic-trained benchmark adapter, not a calibrated real-payment model release.

## 10. Grounded investigator and optional LLM

The `SummaryProvider` interface is already isolated from detection and evidence generation.
`disabled` returns evidence-only deterministic output; `deterministic` selects computed facts locally;
`openai` may select/order IDs from a finite fact list. The server validates that selection and renders
the authoritative fact text. It never accepts provider-invented entities, amounts, scores, or claims.

Configured calls have bounded timeout, retry count, and token output. Missing keys, network/provider
failure, or invalid selected IDs produce an explicit grounded fallback warning, not invented results.
There are no paid calls during startup/readiness. Provider credentials remain server-side. Live paid
provider testing has not been claimed; use the verification log for actual contract-test results.
The provider retains the documented [structured response format](https://developers.openai.com/api/docs/guides/structured-outputs).
Retries are limited to selected transient HTTP/network errors; authentication and invalid-output
errors are not retried. Timeouts are per attempt, not a guaranteed total wall-clock deadline.

## 11. Deployment topology, containers, and CI

The local CLI starts production-compatible Uvicorn without reload, with one worker, disabled raw access
logging, and bounded graceful shutdown. Browser development and production-build preview remain
separate commands; neither requires Docker.

`Dockerfile` builds locked Python dependencies and runs as UID/GID 10001. `Dockerfile.frontend` builds
the locked frontend and uses its production Node/Vinext server, not a Vite development server. The
backend image defaults to production fail-closed identity settings. `compose.yaml` explicitly overrides
these for a **local-only development-principal stack**, not public production. Its services are
PostgreSQL, a one-shot migration, one backend, and the production-built frontend. Database and artifacts
use named volumes. Only frontend/backend are mapped to host loopback; PostgreSQL has no host port.
Set a local-only database password through the shell, then:

```text
docker compose config --quiet
docker compose build
docker compose up --wait
```

Use `/api/v1/health`, `/api/v1/ready`, and `http://127.0.0.1:5173` for stack smoke checks. Preserve the
named volumes when stopping if investigations must survive. Image tags/dependency locks improve
repeatability but are not immutable base-image digest pins or a completed supply-chain audit.

The GitHub Actions workflow checks backend installation/lint/tests/migrations/package builds, frontend
lockfile installation/lint/types/production build/real browser tests, and a local Compose build/smoke
job. It has read-only repository permissions and no deployment step. CI is unexecuted until run on a
GitHub runner; local command results do not imply a green remote workflow.

Docker, Podman, and WSL were unavailable on the development host during this pass. Consequently image
builds, live PostgreSQL migration tests, Compose startup, and an investigation through that stack are
not claimed. These are explicit verification gaps, not reasons to substitute a public deployment.

## 12. Known limitations

- Development principal switching provides no real identity verification. Do not expose the service
  publicly or store sensitive production data in this local configuration.
- Only a validated synthetic `DatasetBundle` is accepted. There is no real-payment ingestion mapping,
  data minimization policy, calibrated loss estimate, or production-model validation.
- Local storage and SQL cannot commit atomically together. A crash between file creation and SQL commit
  can orphan an unreferenced file. Power-loss durability, garbage collection, backup/restore, retention,
  encryption, malware scanning, and cloud-object storage are not implemented guarantees.
- The single scheduler is not safe to multiply across workers/replicas. Abrupt host termination may
  leave an orphan child until the OS/container cleans it up; restart recovery fixes persisted state,
  not distributed process ownership. Training is reproduced per analysis child rather than served by
  a preloaded model service, intentionally preserving the benchmark behavior.
- Upload bytes are bounded, but there are no tenant quotas, global queue bounds, rate limits, or
  pagination guarantees. Large accepted datasets can still consume substantial memory/CPU or timeout.
- Request logging is an operational correlation foundation, not an immutable security audit trail.
- Paid-provider behavior, Docker/PostgreSQL execution, remote CI, and public deployment are not implied
  by local unit/integration/browser success. Dependency findings and their precise scope belong in the
  dependency review and verification records, not a blanket claim of security.

## 13. Phase 5B boundaries

Phase 5B may redesign the frontend around `/`, `/investigations`, and
`/investigations/{id}?run={run_id}` while keeping the backend stable. The centralized client,
session response, typed v1 schemas,
stable IDs, request-aware errors, enqueue/idempotency/poll workflow, persisted candidates, and evidence
queries are the contracts to use. Show queued/running/completed/failed separately, allow empty results,
and do not silently retry enqueue POSTs. Rendering and navigation can change; evidence/model values,
benchmark artifacts, money units, and ownership scoping cannot become frontend guesses.

The Phase 4 demo/replay remains distinct from uploaded investigations. Preserve its prefix-safe graph
and timeline semantics. Do not portray retrospective persisted results as a new streaming detector.
Phase 5A's minimal lifecycle UI is plumbing, not the Phase 5B visual design.

## 14. Phase 5C and later deployment gates

Before real users: implement verified session/OIDC authentication and logout/session expiry; review
CSRF, cookie/security-header/TLS/proxy policy; validate PostgreSQL under concurrency; exercise backups
and restore; establish tenant quotas, retention, privacy, and audit controls; secure object storage;
resolve applicable dependency advisories; test a credentialed provider with bounded cost; choose and
test a durable worker/lease strategy before scaling; add monitoring, readiness/worker supervision, and
incident procedures; validate container builds and end-to-end stack behavior on a Docker-capable host.
Actual-payment ingestion and model calibration need their own validation, not architecture assumptions.

Staging/public deployment and any later frontend redesign are separate authorized phases. This phase
does not configure a public domain or deploy the application.
