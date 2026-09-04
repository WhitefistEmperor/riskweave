# Phase 5A verification log

Baseline: main, clean, HEAD 722ef7abef6937f3fdf9b34bb13dfa1d0c30709d.
Before source edits: 41 Python tests passed (2 upstream deprecation warnings),
Ruff passed, frontend lint/TypeScript/build passed, wheel and sdist built.
All 5 production-browser tests passed in 1.3 minutes after restarting the old
frontend process to load the newly built chunks. Initial browser attempt failed
on missing stale chunks; no test assertions or product sources were changed.

Frozen Phase 3 JSON SHA256:
42c0234331f2b467ccc296f6579478d2feaf7c71e9c159387b6674a09b27e976.

Docker was not found on PATH during baseline inspection; no container validation
is claimed by this record.

## Resumed milestone 2: storage and analysis lifecycle

Resumed from 40f269f without resets or discarding the seven untracked implementation
files. The original resumed suite passed: 47 Python tests, Ruff clean. Added
regressions for exclusive-write UUID collisions and empty attack-progressions at
the upload boundary (the detector/generator were not modified).

After those fixes, all 10 persistence/lifecycle tests passed in 23.62 seconds and
their Ruff check passed. These include a real detector subprocess completing,
an actual timed-out child observed to exit, real worker failure and interruption,
concurrent-start exclusion, owner isolation, idempotency, checksums, upload limits,
and reopening results through a new database engine. No model outputs were mocked
in the subprocess tests. The scheduler remains deliberately single-process.

## Milestones 3–4: API, ownership, configuration and optional provider

64 Python tests passed in 77.50 seconds; Ruff passed. Two upstream TestClient
deprecation warnings remain (httpx and anyio compatibility aliases).
The HTTP tests use real lifespan schedulers and child processes for successful
completion and timeout failure. Typed evidence, grounded investigator calls,
new-app restart persistence, every owner-scoped endpoint, safe errors, CORS,
request correlation, readiness without migrations, upload limits and idempotency
passed. Separate provider tests check disabled mode, explicit opt-in, missing-key
fallback, transient retries, authentication failures and timeout/token settings.
Provider transport tests use fixtures; no live paid model request was made.

## Milestone 5: minimal persisted frontend and dependency remediation

Frontend lint, TypeScript and production build passed on the updated lockfile.
All 8 production-browser tests passed in 1.5 minutes: the 5 original Phase 4
checks plus real upload/enqueue/poll/evidence/investigator/reload and two controlled
UI failure-state tests. The real browser workflow uses generated data and the
actual backend; only error/empty UI states use explicit transport fixtures.
The first attempt passed 7 tests but the real-upload fixture was blocked by
sandbox access to uv's cache. The approved rerun passed all 8 without relaxing
assertions. No visual redesign or benchmark response substitution was performed.

Security updates are recorded in dependency-audit.md. The build retains existing
large-chunk and Vinext route-classification warnings plus a forward-looking Vite
JSON-import warning. These are warnings, not failed checks. No pending npm install
script permission was bypassed; production build succeeded with installed binaries.

## Final local verification and operations foundation

- Full Python suite: **69 passed**, 2 upstream deprecation warnings, 79.42 seconds.
- Ruff: **passed**, including source, tests, and new smoke/sample scripts.
- Frontend: lint, TypeScript, production build and **8 browser tests passed**.
- Wheel and sdist: **built**. The exact current 0.4.0 wheel includes Alembic
  migrations and the byte-identical frozen Phase 3 JSON. An initial packaging
  inspection accidentally selected an older 0.1.0 wheel from ignored dist/;
  the explicit current filename passed. No old artifacts were removed.
- Fresh SQLite migration, repeat application, foreign keys, new-engine reopening:
  **passed** in integration tests; explicit CLI migration also started the live API.
- Additional boundary checks: uniform 400 preflight and 405 method errors,
  wildcard/path/credential-origin rejection, and logging setup for direct Uvicorn
  startup. The full suite above includes these changes.
- Both Dockerfiles parsed (21 and 23 instructions); Compose/workflow YAML and
  loopback ports, service dependencies, and job topology assertions **passed**.
  A parser invocation initially treated the frontend Dockerfile name as a
  directory; passing its file content validated both files. These are static
  checks, **not image builds**.

### Actual HTTP smoke and process restart

`scripts/smoke_platform.py --base-url http://127.0.0.1:8000` used the unchanged
generator, seed 105, 1,000 base payments: **2,824 entities and 1,021 events**.
It observed `queued -> running -> completed`, enqueue time **0.0165 seconds**, and
end-to-end analysis/evidence checks in **16.06 seconds**, with **7 candidate rings**.
This small smoke fixture is not the 5,000-payment benchmark and is not a new
accuracy claim. Computed evidence and the deterministic investigator returned
successfully. Another owner received **404**; malformed JSON received **422** with
the safe error envelope. No paid LLM call occurred.

After actually stopping and restarting the local API on the same database and
storage, `--reopen-run 6a73872a-8471-4b83-b32b-37859b40c767` returned the same 7 rings
and result SHA256:
`14329acdff0c2b8785abf037df614aa2efb0b5146433d514aeb58433e39f588a`.

Detector, feature, generator, experiment, evidence-calculation and frozen result
files have no diff from the Phase 4 baseline. Phase 3 JSON remains SHA256
`42c0234331f2b467ccc296f6579478d2feaf7c71e9c159387b6674a09b27e976`.

### Explicitly unverified gates

Docker/Podman are absent and WSL is not installed: container image builds, live
PostgreSQL migration/concurrency, Compose readiness and container investigation
smoke **could not run**. The original container-build completion criterion is
therefore not certified. GitHub CI is configured but was not pushed or executed.
Three bounded post-update npm advisory requests timed out: its fresh remaining
count is **unavailable**, not zero. Python audit reported no known third-party
vulnerabilities; frontend baseline was 11 packages (8 high, 2 moderate, 1 low),
with targeted updates installed and application compatibility verified. See
dependency-audit.md for exact scope. No public deployment or Phase 5B work began.
