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
- Currency provenance in new results; correct currency precision across findings,
  timelines, evidence and source panels; exact minor units in investigator facts.
  Legacy results with missing currency retain unknown units. Non-INR model scores
  explicitly remain unvalidated. Synthetic uploads cannot bypass currency isolation.
- Run-scoped analyst dispositions, required notes, audit history, safe submission retry
  and revision conflicts. Migration 0002 preserves existing cases; backups retain reviews.
- Owner-scoped whole-case deletion with exact-name/version confirmation, active-job guards,
  atomic metadata erasure and durable file cleanup. Migration 0003 preserves existing cases.
  Explicit bounded retention application excludes active work and open analyst reviews.
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

The analyst-review increment's remote Linux CI also passed all three jobs (run
37108521431), including migration 0002 and a real PostgreSQL-backed review save,
retry and reload with one audit event and unchanged inference-result checksum.

The currency increment passed 114 Python tests and 36 production-browser tests.
Real HTTP tests completed observed JPY analysis, correct currency provenance and
investigator facts, followed by reopen and ownership checks. Browser fixtures verified
USD, JPY, KWD and legacy unknown units throughout findings, evidence and timeline.
The undefined-minor-unit fallback also passed a focused test after the full suite.
Ruff, TypeScript, frontend lint and production build passed. The existing model
artifact digest and historical benchmark were not changed.

The data-lifecycle increment passed the full 126-test Python suite and all 41
production-browser tests. A final cleanup-fairness regression was added afterward;
all 16 focused deletion and backup checks passed, bringing the backend suite to
127 cases. Ruff, TypeScript, frontend lint and production build passed. The real
API smoke completed analysis, review and case deletion, then confirmed that the
case, run and review endpoints returned 404. Migration 0003 and the same deletion
smoke will run against PostgreSQL in container CI. The workflow deletes only its
own newly created smoke case. No deployed/user case was erased by these checks.

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
   organization-specific retention/hold policy, cross-snapshot erasure reconciliation
   and a tested rollback procedure. Case deletion and manual retention commands are implemented.
4. Add ingestion mapping for real source exports; practical dataset and workload limits;
   benchmark deployment capacity. Add worklist review summaries and filtering as usage grows.
5. Evaluate on permissioned real payment data with temporal holdouts, calibration,
   distribution-shift checks, subgroup/error analysis and documented operating thresholds.
   Synthetic results cannot substitute for this validation.

The current executor remains single-host and single-worker. Production scalability,
real-data model performance and completed public deployment are not claimed.
