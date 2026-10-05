# RiskWeave continuation handoff

Updated 5 October 2026. This document is a continuation brief, not a claim that
the project is already deployed or validated on real financial data.

## Latest source and verification

- Current measured-capacity source: `a7a1506141f7e20745f146b2e6ee69af40590aea`, pushed.
  [Linux CI 37254283251](https://github.com/WhitefistEmperor/riskweave/actions/runs/37254283251)
  and PR CI 37254286075 passed all six checks: 249 Python tests, 69 browser tests,
  both containers and actual PostgreSQL inference/restore in both storage modes.
  Production dependency/model inventory is 440,569,347 bytes against 450 MB;
  actual hosted function size remains unverified. Application code is unchanged
  from d5b9e18; this increment adds measured capacity tooling/evidence.
- Three isolated real workers completed/persisted seed-105 controls (1,021/5,104/
  10,207 actual events), using the unchanged trusted model. Checksums verified,
  including historical bb3977... for the smallest control. Largest input 8,232,845
  bytes had worker peak working set 277,712,896 bytes and peak commit 246,018,048;
  worker main 2.82 s, outer process/verification 11.37 s. These are one local Windows
  sample per size, not hosted/whole-system/worst-case/percentile bounds or model accuracy.
  The final rerun corrects a benchmark-only parent provenance mismatch, verifies
  saved model/build metadata against actual worker settings, and reproduces all
  first-run input/result hashes. Private fixture is work/capacity-windows-20261005-v2/.
  See `docs/capacity-baseline.md` and `results/capacity/windows-worker-20261005.json`.
- Release audit `docs/RELEASE_GATES.md` retains the full goal and concrete missing
  evidence. Latest Vercel scoped request still returned 403 requiring re-authentication;
  the Instinct source fetch was inaccessible. No live release or observed data exists.
- Previous diagnostic application source: `d5b9e18a45e6abf31a4e75aa7582e56c47338042`, pushed.
  [Linux CI 37227298824](https://github.com/WhitefistEmperor/riskweave/actions/runs/37227298824)
  and PR CI 37227303053 passed all six checks: 249 Python tests, 69 browser tests,
  both containers and actual PostgreSQL inference/restore in both storage modes.
  Production inventory is 440,566,612 bytes against 450 MB, not hosted bundle size.
  Ruff and all 21 focused feature/temporal tests also passed locally.
- Frozen-model evaluation now reports descriptive shift on all events, independent
  of resolved-label coverage, for each model feature. Causal prefix extraction is
  reused; no test-window diagnostic changes scoring or threshold selection. It has
  empirical CDF/Wasserstein distances, mean/std/ranges and out-of-reference-range
  fractions, with explicit constant-reference nulls. No p-values, confidence
  intervals, universal cutoffs, admission, calibration or retraining is claimed.
- Actual unchanged pinned-model smoke produced diagnostics for 33 features on
  55 validation/49 test synthetic-control events; all previous metrics and the
  selected threshold stayed unchanged. Report is ignored at
  `work/csv-mapping-smoke-20261005/evaluation-with-drift.json`.
- Previous review-progress application source: `43066642662f10a0230b110732eff8b5eb958db3`, pushed.
  [Linux CI 37226537041](https://github.com/WhitefistEmperor/riskweave/actions/runs/37226537041)
  and PR CI 37226539716 passed all six checks: 240 Python tests, 69 browser tests,
  both containers and actual PostgreSQL inference/restore in both storage modes.
  Production inventory is 440,552,028 bytes against 450 MB, not a hosted measurement.
  Intermediate bbd25b1 had a missing readiness import, corrected in this source.
- Local demo database was backed up and migrated explicitly to 0008 with no active
  analysis. API readiness passed after restart; production frontend build passed.
  Browser verification with agent-browser 0.38.2 showed the review column/links,
  explicit legacy unknown totals, successful home navigation and no browser errors.
  No case was deleted. The helper browser was closed; local API/UI remain running.
- Migration 0008 persists candidate totals on new completed runs. Paged worklist
  summaries use only owner-scoped database metadata and the latest completed run;
  no result reads or notes are loaded. Current disposition counts refresh with
  page responses. Older totals remain unknown; new empty results are known zero.
  Browser tests cover run links, unknown totals, refresh and invalid scope/counts.
  See `docs/worklist-review-progress.md`. PostgreSQL restore now includes an
  escalated generated review and verifies the note and worklist summary.
- Previous CSV-mapping application source: `3a7450277386c3cc0ea00fcf0c57aeecfe10374b`, pushed.
  [Linux CI 37225632399](https://github.com/WhitefistEmperor/riskweave/actions/runs/37225632399)
  passed 237 Python tests, 66 production-browser tests, both containers and actual
  PostgreSQL inference/restore. Production dependency/model inventory is
  440,536,682 bytes against 450 MB; actual hosted bundle size remains unverified.
  PR CI 37225634646 also passed; all six exact-source push/PR checks are green.
- Explicit private CSV conversion now supports versioned field mappings, strict
  minor units/timezones/identities/refunds, bounded files/rows, input/output and
  converter hashes, no overwrite and sanitized failures. It imports no labels or
  arbitrary metadata. Missing required source features are rejected, not invented.
  See `docs/csv-payment-mapping.md` and the synthetic mapping example in `schemas/`.
- All 41 focused ingestion/evaluation checks passed (23 new mapping tests).
  An actual unchanged pinned-model command evaluated converted synthetic-control
  CSVs (104 events: 55 validation/49 test), preserving every causal feature and
  all previous evaluation metrics/threshold. Both reports deny production readiness.
  Local smoke artifacts are ignored under `work/csv-mapping-smoke-20261005/`.
- Previous indexed-transport source: `a7f848e9cc8d58f35de40141387bfa87835fe965`, pushed
  to `codex/production-foundation`. [Linux CI 37224837358](https://github.com/WhitefistEmperor/riskweave/actions/runs/37224837358)
  and PR CI 37224840776 passed all six checks: 214 Python tests, 66 browser tests,
  both containers, actual PostgreSQL inference and both PostgreSQL 17 restore
  storage modes, including multipart bounded range reads after restore.
  Production dependency/model inventory is 440,507,313 bytes against 450 MB.
  This remains an inventory check, not a hosted function measurement.
- Migration 0007 records result sizes and fragment digests, with no payload copy.
  Indexed requests verify at most 2 MB per range; incomplete metadata fails closed.
  Legacy indexing requires stopped writers, bounded batches and whole-checksum
  validation. Tests cover active-job/corrupt-object refusal and cascading erasure.
  Read `docs/result-fragment-index.md` before operating the maintenance command.
- Local demo database was backed up, explicitly migrated to 0007 and 17 existing
  results indexed during stopped-writer maintenance. The restarted API returns
  ready/database ready/storage ready. This is local evidence, not deployment.
- Previous evaluation source: `d974b07ffd9f914941e643a2e4d1b47fac62be13`, pushed
  to `codex/production-foundation`. A subsequent documentation-only commit may
  update this handoff; verify the current Git and PR state before continuing.
- [Linux CI 37222724943](https://github.com/WhitefistEmperor/riskweave/actions/runs/37222724943)
  passed 204 Python tests, 66 production-browser tests, both container builds,
  PostgreSQL local/request/SDK background inference and both actual PostgreSQL 17
  backup/restore storage modes. All six push/PR checks passed on this source.
- Twelve new evaluation tests verify label availability/identity, validation-only
  threshold selection, test-label independence, missing-label coverage, metric
  arithmetic, score boundaries, causal scoring prefix and sanitized CLI failures.
  An actual unchanged pinned-model CLI smoke on a declared synthetic control
  evaluated 55 validation and 49 test events with zero missing control labels.
  Reports include input/model hashes, software versions and source fingerprints;
  all explicitly state `production_ready: false`. No real data has been supplied.
- Oversized inline result requests reject before full application reads in both
  storage modes, after owner authorization. Browser tests verify large legacy
  local-mode fallback, UTF-8 reconstruction, fragment/whole checksum rejection
  and cancellation. Actual PostgreSQL restore drills verify storage-size queries
  and the service byte guard. Indexed fragments now use bounded storage ranges; legacy whole-object reads,
  database server work and complete browser allocation remain capacity gates.
- Database-paged worklist reads, owner-scoped counts, literal wildcard escaping,
  Unicode SQLite search, status filtering and page bounds are verified. Browser
  tests cover later-page matches, malformed page metadata, cancellation/revisit
  and refreshing cached history when a case update timestamp changes. Restored
  PostgreSQL drills also verify paged search, literal wildcards and owner counts.
  Local lint, TypeScript, Python lint and the production build passed.
- Backup drills preserve generated input, result checksums, ownership and migration
  state and reject populated restore targets. The operator snapshot also ran in
  the restored PostgreSQL database using a read-only transaction.
- Previous production Python dependency/model inventory measured 440,455,620 bytes against
  a conservative 450,000,000-byte CI budget. Actual hosted function size, memory,
  subprocess support, generated Workflow authentication and capacity remain unverified.
- Local operator report returned schema `0006`, 14 completed runs and no overdue
  work or recent failures. It exposed aggregates only and did not change jobs.
- The requested usage-threshold handoff was prepared at 10% remaining and updated
  through the latest verified source. The full original objective is unfinished;
  continue the numbered release/model/product work below without claiming completion.

## User instructions

- Finish RiskWeave as a complete product/model, beyond its hackathon foundation.
- Close functional, reliability, security, operational and deployment gaps.
- Use Vercel's free tier if Railway is not free. No paid upgrades/resources have
  been authorized. Check actual account allowances before provisioning anything.
- Continue doing useful work autonomously, test it, and push all project changes.
- Keep a handoff file explaining outstanding work and continuation instructions,
  especially when the remaining usage allowance approaches 10%.
- Be quick and communicate concrete results. Never label a partial deployment
  or a synthetic-trained detector as production complete.

## Repository and workspace

- Repository: https://github.com/WhitefistEmperor/riskweave
- Working branch: `codex/production-foundation`.
- Draft PR: https://github.com/WhitefistEmperor/riskweave/pull/1
- Windows checkout:
  `C:\Users\sahil\Documents\Codex\2026-10-03\i-wa\work\riskweave`.
- User-facing outputs:
  `C:\Users\sahil\Documents\Codex\2026-10-03\i-wa\outputs`.
- Python package retains the name `ringsentinel`; product name is RiskWeave.
- Confirm `git status`, `git log -1`, remote branch and PR checks before continuing.
  The version of this file committed on the branch supersedes chat summaries.
- `work/`, model binaries, local databases, logs and runtime state are ignored.
  They are not missing source files and must not be blindly force-added. Never
  commit credentials, analyst tokens, private payment datasets or case snapshots.

## Implemented foundation

- Private offline temporal evaluation with separately resolved labels, input/model
  hashes, explicit missing-label coverage and validation-only threshold selection.
  Synthetic-control command and leakage/identity/CLI tests pass; no real-data
  validation, calibration, retraining or production approval has been achieved.
- Strict unlabeled `payments-v1` ingestion alongside explicitly synthetic bundles.
  Referential validation, refund identity/cumulative limits and currency isolation.
  No fabricated labels on observed data. New results record currency provenance;
  legacy unknown currency stays unknown. Non-INR model validity remains unproven.
- Build-owned joblib artifact, pinned SHA-256, feature compatibility and exact
  scikit-learn version checks. Never load an analyst-uploaded executable model.
- Versioned API, owner-scoped investigations/artifacts/runs/results/evidence,
  idempotent start, safe public errors and request IDs.
- Separate public synthetic demonstration surface; production disables it.
- Analyst dispositions, required notes, revision conflicts, idempotent audit
  history, save/reload and unchanged inference-result checksums.
- Exact-name/version whole-case erasure, active-work guards, transactional
  database object deletion and durable local file cleanup. Manual retention
  commands exclude active work and open investigations/escalations.
- Browser OIDC authorization-code/PKCE, callback/logout, tab session storage,
  expiry handling; API RS256 public-JWKS/issuer/audience/scope validation.
  An actual identity provider has not been provisioned or live-tested.
- Optional operator-selected HTTPS JWKS with bounded retrieval, per-process cache,
  throttled refresh, atomic key retirement and expired-cache outage rejection.
  Real-signature rotation tests pass; live provider rotation remains unverified.
- Native Next.js 16.3.8 console, standalone non-root Docker build.
- Owner worklist name/case-ID search and case-status filters across loaded pages,
  first-page reset, explicit unmatched results and cached history reads restricted
  to ten visible cases. The new database-paged endpoint scopes counts to the owner,
  bounds page/search parameters and escapes literal wildcard characters. See
  `docs/worklist-pagination.md`; hosted and legacy capacity remain outstanding.
- Per-request nonce script CSP, dynamic/private document rendering, explicit OIDC
  connection origins, blocked inline handlers and unconfigured external connections.
  Inline styles remain allowed for component positioning; verify hosted auth/CDN.
- Optional private database object storage, atomic global byte admission,
  checksummed reads, offline verified file import and backup/restore tooling.
- Request-mode global SQL execution claim, killable bounded subprocess,
  queue/execution deadlines, scoped recovery and fencing of late results.
- Private 2 MB upload parts, saved-part resume/discard/expiry, whole-file
  validation/SHA-256 and atomic artifact acceptance. Inline result reads admit
  at most 2 MB after owner authorization and object-size inspection; oversized
  results use verified fragments, including older local-mode console runs.
  Private result manifests
  and base64 fragments with fragment and complete-object integrity verification.
- Optional Python Vercel Workflow adapter with transactional delivery intent,
  30-second submission leases, bounded retries/backoff, monthly start admission,
  daily/hourly recovery, provider-status repair and no browser execution dependency.
  A changed model digest fails a queued run rather than changing its provenance.
  Erasure removes dispatch intent; stale steps cannot resurrect a case.
- Alembic head is `0008`; upgrades preserve populated cases/reviews/foreign keys.
- CI covers backend, native frontend and isolated PostgreSQL/container workflows.
- Private read-only operator snapshot counts runs, overdue execution/delivery and
  recent failures, with sanitized CLI exit codes and no case details. PostgreSQL
  transactions are read-only. External alerts/scheduling still require deployment;
  see `docs/operator-monitoring.md`.
- PostgreSQL backup/restore drill now targets isolated CI databases with matching
  PostgreSQL 17 clients, generated lifecycle fixtures, local/database object modes,
  owner/checksum/migration preservation and existing-target rejection. The latest
  verified Linux source passed both cases; this Windows host skips them.
- Dedicated Vercel ASGI entry, Python 3.13, cached build-owned model, checksum
  admission in API and Workflow steps, disposable scratch and daily cron config.
  Private workspaces are excluded; CI checks production dependency inventory.
  Actual hosted bundles and generated queue authentication remain unverified.

Read these documents before redesigning anything:
`docs/production-progress.md`, `docs/vercel-deployment.md`,
`docs/request-execution.md`, `docs/background-delivery.md`,
`docs/bounded-transport.md`, `docs/result-fragment-index.md`, and the existing
security/model/backup documentation.

## Verification and model caveats

The next packaging increment passed all 172 Python tests locally, Ruff and
source/wheel builds. Eight release tests cover cached model preservation,
tamper rejection before deserialization, override rejection, incomplete caches
and production identity/demo admission. Linux production inventory and hosted
packaging are separate checks; consult current PR CI for the exact pushed SHA.

The previously fully passing remote baseline is commit
`df45a981308b62f15a598bdc829e2310c3932324`, CI run `37187259202`:
151 Python tests, 55 production-browser tests, both container builds, and actual
PostgreSQL local/request analysis, review and erasure.

The background increment adds 13 backend and 3 browser checks. Its initial full
local regression passed 163 tests and exposed one outdated schema-table assertion;
that assertion was updated for migration 0006. All 18 final dispatch/persistence/
PostgreSQL-DDL checks passed. All three focused background browser checks passed;
lint, Ruff, TypeScript and the rebuilt production console passed. Real local SDK
HTTP smoke completed model inference without posting `/execute`, with review,
owner isolation, complete erasure and the unchanged result checksum below.
Consult the PR for the latest full browser suite and remote CI outcome; do not
infer a passing hosted release from these local checks.

The trusted existing local model digest is
`182c06741a7fae5c389e79c8ea7c2888027528ab92ddde4479588805e0187c74`.
The stable generated seed-105 smoke result checksum is
`bb3977a6d8dfaa71cb5190b83724d3c6fa11137bf700745336fb10278585f37c`
(1021 events, 2824 entities, seven candidates). These are synthetic regression
facts, not performance evidence on real payment populations. Do not inflate
accuracy, calibration, fraud certainty, recoverable loss or production readiness.

The Workflow Python SDK is pinned to `vercel-workflow==0.11.0` and is beta.
Read the installed package and current primary docs rather than old JS-only
instructions. The local SDK queue needs an AnyIO scope owned by its root task;
starting it in a normal FastAPI request breaks scope teardown.
`scripts/serve_background_test.py` supplies that lifecycle only for isolated tests
and refuses production/managed Vercel mode. Product code uses public SDK APIs;
private world reset/cleanup imports are confined to tests. Production rejects
the embedded queue. Do not deploy the test harness as a durable worker.

## Hosting and access blockers

- Target: Vercel Hobby, account/workspace
  `sahilsinghkushwah10thb-9948s-projects`.
  No RiskWeave Vercel project or verified live deployment currently exists.
- Access rechecked on 5 October: the Vercel connector can list the unrelated
  project, but team/Git context remains empty. Explicit access to the target
  team returns 403 requiring re-authentication to that workspace; a RiskWeave
  search without team scope returns no accessible projects. No RiskWeave project exists and
  the CLI was not authenticated. Browser import of the tested branch URL
  returned "Could not access the repository. Please ensure you have access to it."
  Account listing access does not establish permission to import this repository.
- Browser import needs GitHub connection. Its connection popup previously had an
  invalid URL and browser policy rejected it. The human was asked to complete
  GitHub connection manually and reply `connected`; no such reply was received.
  Never bypass that rejection via CDP, another browser or a substituted auth route.
  Recheck only through authorized supported tools after access changes.
- An unrelated Vercel project, `synapse-ps-selection`, must not be modified.
- Railway offered a limited trial. Initial private API deployments were stopped
  and verified offline; repository source was disconnected. Empty database volume
  and service definitions remain and can consume trial allowance. No user cases
  were migrated there. Do not upgrade Railway or claim it hosts this release.
- No free private PostgreSQL provider or live identity issuer is configured yet.
- User source link
  https://files.instinct.com/file-01M3Z91EVRMY9WNSX7G8R51ARE
  required authentication/phone sign-in/terms, so its contents were not read.
  Do not invent requirements from it or accept terms/login on the user's behalf.

## Next work, in order

1. Verify the pushed branch/PR checks and preserve the passing source. Fix concrete
   failures before release. Update this file with exact tested commits/results.
2. Finish free-account access and provisioning. Import the tested branch into
   Vercel with console root `frontend`. Establish a private TLS PostgreSQL
   database with verified free storage/transfer allowances and explicit budgets.
3. Verify the implemented Python API packaging on Vercel: root `app.py`, Python
   3.13, build-owned model/manifest, production admission and `/tmp` scratch,
   authenticated generated Workflow queue functions, duration, memory, bundle
   limits and routing. See `docs/vercel-deployment.md`. CI's conservative inventory
   is not a hosted bundle measurement. Configure both cron secrets identically.
   Normal filesystem/scheduler defaults are unsafe for serverless; the dedicated
   entry point requires database/request/managed-workflow mode explicitly.
4. Apply migrations explicitly through 0008 and provision a live OIDC provider.
   Align issuer/audience/scope/JWKS and registered exact HTTPS callbacks/logout.
   Verify the implemented bounded HTTPS public-key cache/rotation against that
   provider, including overlap, removal, outages and cache expiry; see
   `docs/authentication-key-rotation.md`. No public dev identity/demo in prod.
5. Configure the backend daily recovery cron and matching private cron secrets.
   Default admission is 50 analysis starts/month and 10 pending managed runs
   unless overridden. These are application guards, not provider billing caps.
   Verify Hobby/account-wide quotas, SDK event counts, retention and generated
   function access controls before calling background execution durable in hosting.
6. Verify the full HTTPS workflow on the exact deployed commit: real login/expiry/
   logout, upload >4.5 MB via parts, real frozen-model inference, close browser,
   reload, verified result fragments, evidence, review retry/conflict, two-user
   isolation and case erasure. Exercise process interruption, queue publish loss,
   duplicate delivery, deadline fencing, rollback and restore against hosted PG.
7. Benchmark actual deployment memory/latency/input bounds. Indexed fragment endpoints use bounded reads; legacy results still use
   whole-object verification until explicit indexing. The browser assembles
   complete objects. Large legacy evidence, candidate and investigator replies still need
   bounds/capacity review. Verify subprocess support/termination in Python Functions.
8. Add external readiness/queue/error monitoring and alerts, scheduled encrypted
   backups, restore drills, rollback and operator runbooks. Define retention/holds
   and erasure across exports/snapshots/provider workflow histories. The hourly
   reconciler does not delete expired case data automatically.
9. Use the new offline frozen-model workflow in `docs/real-data-evaluation.md`
   and validate the detector on permissioned real data: review actual source semantics
   against the new CSV mapping contract, then use temporal
   holdouts, leakage controls, calibration, threshold costs, subgroup/error analysis,
   distribution shift and documented operating limits. Real-data evaluation needs
   authorized data; never fabricate results to fill that gap.
10. Complete product gaps supported by actual usage: review workflows beyond the implemented worklist summaries,
    hosted/legacy capacity, permissions/teams where required, accessible onboarding,
    practical exports and operator documentation. Preserve evidence traceability.

## Working instructions for the next assistant

Continue implementation, not just planning. Preserve existing work, read relevant
repository instructions, and use meaningful tests for changed behavior. Never
force-push, merge the draft PR, erase actual cases, expose a dev API publicly or
introduce paid services without the necessary authorization. Stop at a real access
or legal-terms gate; explain it precisely while completing independent code work.
Do not ask repetitive confirmations for already authorized reversible coding work.
Keep model/operational/deployment claims separate and backed by evidence.

Useful commands from the checkout:

```text
git status --short
git log -1 --oneline
gh pr checks 1
uv sync --locked --extra dev
uv run --no-sync ruff check .
uv run --no-sync pytest
uv build
```

From `frontend`: `npm ci`, `npm run lint`, `npm run typecheck`, `npm run build`.
Start the explicitly migrated development backend and production console before
`npm test`. Browser verification must use the current build. For disposable
PostgreSQL checks use the CI/Compose recipes; never point smoke tests at user data.
The smoke tool accepts only loopback URLs and deletes only its own generated case.

Suggested prompt to paste into Claude:

> Continue RiskWeave from the pushed codex/production-foundation branch and PR 1.
> Read docs/CLAUDE_HANDOFF.md and the linked deployment/security documents first.
> Verify Git status and CI, then finish the highest-priority remaining work. Use
> Vercel's verified free allowance, preserve all existing code and model provenance,
> test behavior, and push project changes. Do not claim hosted production readiness
> until the exact deployed commit passes the full authenticated workflow, recovery
> and restore checks. Report access/data blockers honestly and continue independent
> work instead of inventing success.
