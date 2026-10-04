# Product completion work — 4 October 2026

## Implemented

- Fresh nonce script CSP on dynamically rendered/private console documents,
  including missing document routes; explicit identity connection origins and
  blocked unconfigured connections. Inline UI styles remain permitted. Verify
  the hosted gateway and live identity workflow before release.
- Optional fixed HTTPS public-JWKS retrieval and rotation, bounded response/cache,
  refresh throttling, atomic key replacement and fail-closed expired-cache outages.
  Static-file mode remains available. Live-provider lifecycle tests remain required.
- Dedicated Vercel Python 3.13 release entry point and build-owned model bundle,
  cached-byte preservation, strict production admission and identical model admission
  in Workflow steps. Function duration, private-workspace exclusions and daily cron
  are configured. CI checks a conservative production dependency inventory; actual
  provider-generated bundle sizes and hosted behavior remain release gates.
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
- Native Next.js 16.3.8 builds for Vercel and a non-root standalone container.
- Optional database objects with atomic byte admission, artifact/result persistence
  and case erasure; offline verified import preserves old keys and source files.
- Optional request execution with owner-scoped dispatch of an existing run, a
  global single-analysis capacity slot, deadlines, late-result fencing and scoped
  recovery. Migration 0004 preserves populated review history and foreign keys.
  See [configuration and remaining serverless gates](request-execution.md).
- Optional Vercel Workflow delivery with atomic SQL intent, submission leases,
  bounded retries/backoff, monthly admission and daily/hourly recovery. Managed
  runs no longer require browser execution. SDK steps retain owner/claim checks,
  model-version provenance, deadlines and erasure fencing. Migration 0006 preserves
  existing cases. See [background behavior and hosted gates](background-delivery.md).
- A [Claude handoff](CLAUDE_HANDOFF.md) records continuation instructions, verified
  evidence, free-hosting constraints, access blockers and remaining acceptance work.

## Verified so far

Authenticated fragment transport now supports staged uploads, saved-part resume,
discard and expiry, shared byte admission, complete dataset validation and atomic
artifact acceptance. Migration 0005 adds private upload sessions without rebuilding
existing case/review tables. Request-mode result delivery verifies fragment and whole
checksums before displaying findings. See [transport behavior and limits](bounded-transport.md).
Hosted capacity and managed background dispatch verification remain release gates.

The background increment's first full local Python run passed 163 tests and found
one obsolete table-list assertion. After updating it for migration 0006, all 18
final dispatch/persistence/PostgreSQL-DDL checks passed. Three focused production
browser checks passed. The real local SDK HTTP smoke completed analysis without
posting `/execute`, with review reload, owner isolation, erasure and the unchanged
frozen-model result checksum. Ruff, lint, TypeScript, production build and wheel/
source packaging passed. The current suites contain 164 backend and 58 browser
checks; consult the pull request for full-suite and container CI results.

Local transport validation passed a full 148-test backend regression, then the
three added session-history, metadata-rollback and streamed-size regressions.
The browser suite passed 53 cases; a synthetic fixture was updated to include
the new pending-upload route. Four final focused checks passed against the rebuilt
console, including that fixture, resume/discard and the new expired-key retry check.
The current CI suites contain 151 backend and 55 browser tests. Ruff, TypeScript,
frontend lint and the final native production build passed. PostgreSQL/container
transport validation is tracked on the pull request; local checks alone do not
establish a hosted Vercel release.

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

Vercel Hobby is selected following the user's free-hosting instruction. Railway
provided a time/credit-limited trial; both initial private deployments were stopped
and verified offline, and the API repository source was disconnected. The empty
database volume and service definitions remain, and retained storage can consume
trial allowance. No application cases were written there.

No Vercel project/deployment has completed. The connector cannot access the Hobby
workspace; repository import in the signed-in browser requires GitHub connection.
The user has been asked to complete that connection after the browser rejected
its popup's invalid URL. No paid resource or plan upgrade has been selected.
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

The default executor remains single-host and single-worker. Request execution
has distributed database claims, bounded upload/result transport and optional
workflow delivery. Managed hosting still needs dispatch interruption/recovery,
hosted runtime/bundle/capacity validation and actual provider configuration. Production
scalability, real-data model performance and completed public deployment are not claimed.


## Indexed result delivery, 5 October 2026

Source a7f848e9cc8d58f35de40141387bfa87835fe965 passed all six push/PR checks.
Linux CI 37224837358 passed 214 Python and 66 browser tests, both containers and
actual PostgreSQL 17 backup/restore with multipart ranges in both storage modes.
Migration 0007 adds per-fragment digests and result sizes without payload copies.
Requests authorize ownership and verify at most 2 MB per indexed range; incomplete
metadata fails closed. A maintenance CLI verifies and indexes bounded legacy batches
with all writers stopped. Local demo migration/indexing completed for 17 results;
readiness passed after restart. The new production inventory is 440,507,313 bytes.
Legacy full reads, database server work, browser reconstruction and actual hosted
capacity remain gates. Vercel scope access still returned 403 on 5 October.


## Explicit CSV source preparation, 5 October 2026

Source 3a7450277386c3cc0ea00fcf0c57aeecfe10374b adds private offline CSV conversion
with versioned explicit mappings, strict minor units/timezones, source/output and
converter hashes, canonical cross-record validation, no overwrite and sanitized
failure handling. Unknown labels and arbitrary source metadata are not imported.
Missing required source identities/history/retry counts remain a source-adapter gate.
All 41 focused ingestion/evaluation tests passed, including 23 new mapping tests.
The unchanged pinned-model CLI evaluated a converted 104-event synthetic control
with exact causal-feature and metric/threshold preservation. This is command-path
regression evidence, not observed-data validation. CI 37225632399 passed 237 Python
and 66 browser tests, both containers and actual PostgreSQL inference/restore.
Production inventory is 440,536,682 bytes; hosted packaging/capacity remain unverified.


## Worklist review progress, 5 October 2026

Application source 43066642662f10a0230b110732eff8b5eb958db3 passed all six push/PR
checks: 240 Python tests, 69 browser tests, both containers and actual PostgreSQL
inference/restore. Migration 0008 saves candidate totals at completion. The owner-
scoped worklist aggregates current dispositions for the latest completed run
without loading result bytes or notes. Legacy totals remain explicitly unknown;
new empty results are zero. New runs do not inherit old reviews, and queued/failed
runs do not obscure the most recent completed review. Browser checks cover run
links, refresh and invalid summary rejection. PostgreSQL backup tests now preserve
an escalated review/audit note and verify the restored worklist summary in both
storage modes. Local migration, readiness, production build and direct browser
verification passed. Inventory is 440,552,028 bytes; hosted capacity remains open.


## Label-independent temporal feature diagnostics, 5 October 2026

Source d5b9e18a45e6abf31a4e75aa7582e56c47338042 adds descriptive validation/test
input shift for every feature used by the frozen model. All events count regardless
of resolved-label coverage, using the same causal scoring prefix. Marginal CDF and
Wasserstein distances, ranges/means/population standard deviations and out-of-range
fractions have no p-values, automatic admission thresholds or approval claims.
Constant-reference standardized changes are null. Nine new tests compare hand
arithmetic and independent library distances, reject invalid numeric inputs and
verify half-open windows and private output. All 21 focused evaluation tests passed.
An actual unchanged pinned-model synthetic-control command produced all 33 feature
diagnostics for 55 validation/49 test events with unchanged metrics and threshold.
Full CI results are recorded in the current continuation handoff.

Exact-source CI 37227298824 and PR CI 37227303053 passed all six checks: 249 Python/69 browser tests, both containers and actual PostgreSQL inference/restore. Inventory: 440,566,612 bytes; actual hosted packaging remains unverified.
