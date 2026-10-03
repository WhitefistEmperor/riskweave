# Product completion work — 3 October 2026

## Implemented

- An unlabeled `payments-v1` contract, without fabricated outcome labels or generator
  metadata. Upload and worker both validate it. Synthetic uploads remain supported.
- Referential checks shared with the synthetic contract, stricter refund identity,
  currency and cumulative-value checks, and single-currency observed datasets.
- Build-owned model artifacts with a pinned digest, feature compatibility and exact
  scikit-learn-version checks. Artifact inference replaces per-run synthetic retraining
  when configured. Container builds now generate their artifact once.
- Artifact SHA-256 in run provenance and explicit propagation to the worker.
- Run-scoped analyst dispositions, required notes, audit history, safe submission retry
  and revision conflicts. Migration 0002 preserves existing cases; backups retain reviews.
- Browser OIDC authorization code with PKCE, sign-in callback and sign-out, using
  `oidc-client-ts`. Tokens live in tab-scoped session storage, never local storage.
  Expired or missing tokens return the browser to sign-in; the API still authorizes
  every protected operation. No refresh-token scope is requested.

## Verified so far

The initial full Python regression passed 101 tests. Added artifact round-trip and
tamper checks passed alongside ingestion checks (6 tests). Both synthetic and unlabeled
uploads completed the real worker lifecycle using the frozen artifact and reopened
persisted evidence successfully (2 tests). Frontend typecheck, lint and production
build passed. Final full Python regression passed 104 tests; the production-browser
suite passed 27 tests. OIDC configuration security checks were added afterward and
run separately. Live-provider and image/runtime validation remain outstanding.

The analyst-review increment passed 109 Python tests and all 31 production-browser
tests, including a real upload, analysis, review save and revisit. TypeScript, Ruff,
frontend lint and production build passed. The local API smoke verified idempotent
review writes, ownership isolation and unchanged result checksums. Its container-CI
counterpart also exercises review persistence against PostgreSQL. A Windows process
termination race was fixed and the worker-lock cleanup regression passed.

The previous increment's Linux CI passed backend, frontend and both container builds
with a real PostgreSQL-backed analysis (run 37106573152). Current remote validation
is tracked on pull request 1; local checks alone do not establish production readiness.

## Deployment state

A private Railway project named RiskWeave was created in the connected personal
workspace. No application service or database has been deployed. Repository attachment
requires the user's confirmation under the Railway deployment tool's instructions.
The browser identity flow is implemented but an actual provider has not been provisioned
or live-tested. Model artifact loading is only safe for trusted build artifacts;
joblib is executable serialization and must never accept user-uploaded model files.

## Remaining acceptance work

1. Confirm repository and finish provider configuration, token issuance, audience,
   scope, public-key provisioning, login/logout/expiry and two-user isolation tests.
2. Deploy PostgreSQL and durable artifact storage, run explicit migrations, verify
   private API routing and TLS, and exercise restart, interrupted-job recovery and restore.
3. Establish external uptime/error/queue monitoring, alerts, scheduled encrypted backups,
   retention/deletion operations and a tested rollback procedure.
4. Add ingestion mapping for real source exports; practical dataset and workload limits;
   benchmark deployment capacity. Add worklist review summaries and filtering as usage grows.
5. Evaluate on permissioned real payment data with temporal holdouts, calibration,
   distribution-shift checks, subgroup/error analysis and documented operating thresholds.
   Synthetic results cannot substitute for this validation.

The current executor remains single-host and single-worker. Production scalability,
real-data model performance and completed public deployment are not claimed.
