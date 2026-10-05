# RiskWeave continuation handoff

Updated 5 October 2026. This document is a continuation brief, not a claim that
the project is already deployed or validated on real financial data.

## Instructions for Claude at the usage handoff

Use repository WhitefistEmperor/riskweave, branch codex/production-foundation,
draft PR #1. Read this file and docs/RELEASE_GATES.md first. The tested application
commit is 144fbd4; documentation may have a newer head. Inspect git status and
remote CI before editing; preserve local/private fixtures and all user cases.
The current goal is still the complete deployed product and validated model.

1. Local queue backfill is now applied and verified (see latest proof below).
   Apply --upgrade-queue to other supported deployments only after private backup
   and stopped-writer checks, preserving original hashes/reviews. Current
   new-run metadata does not automatically rewrite legacy rows. Add dense-case
   response, memory and actual PostgreSQL measurements, not only sparse controls.
2. Implement an exact decimal-string monetary contract through API/UI if totals
   exceed JavaScript safe integers. Do not silently round financial amounts.
3. Restore supported Vercel scope/repository access and verify free allowances,
   private TLS PostgreSQL and a real identity issuer. The connector previously
   returned 403; deployment is not verified. Do not bypass the rejected auth popup.
4. Apply migration 0010 explicitly with writers stopped; configure hosted workflow,
   cron and secrets. Verify full HTTPS login/expiry/logout, owner isolation, upload,
   browser-close analysis, review/conflict/erasure and interruption/restore on the
   exact source. Do not merge the draft or purchase upgrades without authorization.
5. Establish off-host encrypted scheduled backups, alert destinations, external
   monitoring, rollback and recovery/retention ownership. Manual drills do not
   establish hosted RPO/RTO or scheduled operations.
6. Obtain authorized observed exports and independently resolved/matured labels.
   Use documented temporal evaluation, calibration and error/subgroup/shift gates.
   Analyst dispositions and synthetic controls are not observed fraud truth.
7. Read the original Instinct source only if supported access is restored; its
   requirements remain unknown. Keep this GitHub handoff current with exact commits,
   test results, failed checks and blockers, including incomplete work.

No trained artifact, private case data, credentials or encryption keys belong in
Git. Local trusted generated model exists under ignored work/models; build/release
reproduction is in docs/vercel-deployment.md. Source/main and unrelated projects
must not be substituted for the tested branch. Latest usage snapshot is below.

## Latest source and verification

### Applied local maintenance and real saved-case backup/restore

Source 4616e80 (tested application 144fbd4) was idle: zero active analyses/open
uploads/pending deletion tasks. Its owned API was stopped. A standard manifest-format
private snapshot was created under work/browser-queue-maintenance-20261005/snapshot/;
this is separate from the earlier raw 0008-to-0010 safeguard. Original fingerprints
are privately saved beside it; no case content or identifiers are committed.

Explicit --upgrade-queue upgraded all 18 older indexes across 19 completed saved
runs; a second pass returned zero. It added 839 section metadata rows. Every other
table count, original result reference/checksum/provenance fingerprint and review/
audit fingerprint matched before maintenance. SQLite integrity passed. All snapshot
manifest and live object hashes were verified. Every saved queue was read with
whole-object reads forbidden; the largest scalar range read was 18 bytes.

The actual pre-maintenance snapshot was restored into a different new private
SQLite/object directory (39 files). All original table counts and run/review/audit
fingerprints matched; integrity passed. The live database was never overwritten.
This local plaintext backup/restore is not encrypted/off-host/scheduled recovery
or a hosted RPO/RTO claim. Preserve these private directories until an operator
sets retention; never push them to GitHub or erase user cases for a fresh start.

API restarted on tested source: session79521 / PID24556, log
work/queue-maintained-api.log, build_commit4616e80, unchanged trusted model/local
jobs. Frontend remains production session96900. /api/v1/health and /api/v1/ready
returned200. An actual owner-scoped queue returned seven candidates in1,211 bytes;
another owner received404. No schema migration or original-case deletion occurred.
See results/operations/local-queue-maintenance-20261005.json for aggregate proof.
Both 4616e80 source CI runs 37268084760/37268088840 passed before maintenance;
latest application proof remains295 Python/74 browser tests and both encrypted PG
restore modes. New documentation CI after this push must be inspected separately.

Usage window reset: the previously requested10% handoff was already pushed. Keep
this file on GitHub current. Next implementation gap is exact decimal-string
monetary values through the persisted API and frontend; large legitimate totals
must not be silently rounded or rejected just to make tests pass. Dense/browser/
hosted capacity and Vercel/private DB/live identity/operational/observed model gates
remain open. This maintenance only closes the existing local queue backfill step.


### Queue backfill continuation checkpoint

Pushed application source `144fbd4432205f80a68c26efcdf3fc9429889a82` adds explicit --upgrade-queue to the stopped-writer section index CLI.
It selects completed runs whose queue marker is absent/false, verifies original
hash/size/canonical bytes and every existing index row, then atomically replaces
metadata and sets the current marker. Corrupt/missing declared index rows and
active analyses are rejected; original bytes/references/checksums/reviews survive.
No schema migration, API-request rewrite or actual-case maintenance is automatic.
See docs/targeted-result-sections.md for the exact private backed-up command.

All 28 section tests passed locally before a strengthened rollback assertion;
its four upgrade checks subsequently passed after testing rollback following
actual metadata deletion/replacement. The final focused rerun passed all four upgrade checks in both stores. PostgreSQL SQL compilation passed; the real encrypted PostgreSQL
backup/restore drill now also upgrades older queue metadata and reopens bounded
summaries. [Source CI 37267639816](https://github.com/WhitefistEmperor/riskweave/actions/runs/37267639816)
and [source CI 37267642951](https://github.com/WhitefistEmperor/riskweave/actions/runs/37267642951)
passed all six checks: 295 Python tests, 74 production-browser tests, containers,
actual PostgreSQL inference/SDK background delivery and encrypted restore in both
storage modes. PostgreSQL now executes the legacy queue upgrade before backup,
then verifies restored bounded summaries with whole-object reads disabled.
No frontend retry was required. Production inventory is 440,766,010 bytes against
450 MB; actual hosted bundle remains unverified.

Application UI remains a917dd4's verified production build (291 Python/74 browser
checks). New source CI is verified; inspect later commits before continuing maintenance.
Before applying backfill to existing actual cases, stop all writers, verify a private
backup and preservation fingerprints, run bounded maintenance, confirm hashes and
reviews, then restart the tested source. Current loopback API remains session3405
and frontend96900 on a917dd4; no maintenance was run on their actual saved cases.
Remaining full-release gates: exact large monetary contract, dense/browser/hosted
capacity, supported Vercel access/private DB/live identity, workflow/cron/monitoring/
scheduled off-host recovery and authorized observed model approval.


### Current bounded-queue implementation checkpoint

Pushed source `a917dd492c3e850f12eaf59fdeb42db6a8be0779` adds /runs/{run_id}/queue-page and changes the console
queue to five bounded summary fields (ID, score, exposure, member/event counts).
New result metadata indexes two verified scalar ranges and two derived counts;
no schema migration beyond 0010, model change, original-byte change or user-case
rewrite. Full selected candidate/evidence remain fragment-accessible. Derived
counts trust committed DB metadata; they are not cryptographic array-count proofs.
Older indexes/API routes preserve fallback, so bounded legacy server memory still
needs explicit stopped-writer metadata maintenance. Exposure values above the
JavaScript safe-integer range need an exact decimal-string UI contract.

All 24 focused Python section tests passed, including 100,000 member IDs with
under-500-byte queue output and only two <100-byte scalar reads, pagination,
owner denial, missing metadata and real HTTP contracts in both storage modes.
Frontend lint/typecheck/production build passed. All 14 targeted browser checks passed against the production build, including
actual upload/analysis/evidence/review/revisit, four keyboard widths, queue
navigation/reload, cancellation, digest rejection and malformed queue counts.
[Source CI 37266028723](https://github.com/WhitefistEmperor/riskweave/actions/runs/37266028723)
and [source CI 37266033354](https://github.com/WhitefistEmperor/riskweave/actions/runs/37266033354)
passed all six checks: 291 Python tests, 74 production-browser tests, containers,
actual PostgreSQL inference/SDK background delivery and encrypted restore in both
storage modes. Neither frontend needed a retry. Production dependency/model
inventory is 440,748,536 bytes against 450 MB; hosted bundle size is unverified.

Capacity-source 84eb428 CI 37265235086 and 37265237758 failed their frontend job:
real browser analysis status matched two elements because the evidence-progress
output has an implicit status role. This source replaces that wrapper with a div
live region, retaining progress announcements. Both earlier cc38ca4 CI runs passed;
retain the new failure and verify the fix rather than retrying it away.

Owned local API was idle (zero active analyses/open uploads) before restart.
API session 3405, log work/bounded-queue-api.log; frontend production session 96900.
No database migration or actual-case deletion occurred. Latest usage snapshot is
9% current-window remaining / 56% weekly remaining (10% threshold reached). This handoff is maintained on
GitHub before reaching the requested 10% threshold; copy it into Claude with the
branch codex/production-foundation and preserve the full release gates below.

Next: preserve the verified source, inspect newer checks, add explicit queue
metadata backfill for legacy indexed results and remeasure denser summaries and
selected sections. Vercel account access, private database/live identity, hosted
workflow/cron/monitoring/scheduled backups and authorized observed model validation
remain open. Do not replace the objective with passing synthetic controls.


### Latest capacity evidence, after the frontend changes

A fresh isolated worker baseline on cc38ca45f7ea8aca753ffbe9e27c2139da19ca58
(application source 134c67c) reproduced all historical input/result hashes for
1,021/5,104/10,207 generated events. Peak worker working sets were 202.9/248.5/
278.0 MB; worker main times 0.65/2.29/4.34 seconds. This includes current section
and overview indexing; earlier capacity records predate these changes. Neither
sample establishes hosted capacity or a causal index-overhead estimate.

New scripts/measure_indexed_reads.py measures the saved synthetic results without
migration/jobs or whole-object reads. Three repetitions per path verified overview,
first eight-item page and largest evidence chunk/final hashes. Overview read 93–95
bytes; pages read 6,146–16,041 bytes. Evidence manifest plus delivery verified the
containing source fragment twice, reading 91,032/459,698/283,338 bytes internally.
This bounded amplification is preserved, not hidden by an evidence cache.

Public aggregate reports: results/capacity/windows-worker-indexed-20261005.json
and indexed-reads-20261005.json. Reproduction, medians and exclusions are in
 docs/capacity-baseline.md. Driver lint and the actual measurement passed; this
commit changes measurement tooling/documentation only. Application CI remains
134c67c: 289 Python/73 browser checks, all six jobs passed. Inspect newer CI after
this push; do not claim unobserved checks. Private fixture is
work/capacity-paged-20261005/ (never use it as production data).

Next independent gap: a candidate page limits item count but can still contain
very large membership/event arrays. Design a bounded queue-summary contract while
preserving full selected-candidate fragment access; verify dense cases, response
sizes and browser memory. Investigator selected sections and actual PostgreSQL/
provider costs also require capacity work. Vercel access, live identity/private DB,
monitoring, scheduled off-host restore policy and authorized real-model validation
remain incomplete. Preserve the full goal and release gates below.


### Current continuation checkpoint — email investigation and frontend integration

The four latest RiskWeave GitHub failure emails were read through the connected
Gmail account on 5 October 2026. They are historical CI notifications, not proof
of a failed live deployment:

- 799e75b, push run 37261238329: frontend keyboard selection at 1024px failed.
  Its failed-job retry passed; do not call the initial failure fixed solely by retry.
  Trace keys occurred within 18 ms of opening the select, with ArrowDown and Enter
  only 3 ms apart. Current work adds observable open/option/focus waits, retaining
  the final selected-entity assertion; browser verification is pending.
- 6f8c578, push 37260047761 and PR 37260050224: persistence test expected the
  old exact table list. Corrected in ab475ae; subsequent complete CI passed.
- 19d6917, push 37255956899: adversarial encrypted archive fixture omitted
  persisted object files. Fixed in 36bcc25; later encrypted restore checks passed.

Pushed application source `134c67cc60de33560edb921ff255c606bdce03fd` adds a verified lightweight
owner-scoped overview endpoint, eight-item candidate pages in the console and
checksum-verified selected candidate/evidence chunks with cancellation and stale
selection protection. It preserves full analyst review, evidence, timeline and
investigator flows. Original bytes/model hashes are unchanged. No new migration
is required beyond 0010. Older indexed scalar metadata has a server whole-result
fallback; an older API's overview 404 enables legacy browser transport. Other
errors fail closed. Graph loading remains lazy.

Verified locally: lint, typecheck, production build; 22 section tests across both
stores including overview HTTP/owner denial; all 10 focused browser checks at four
widths plus new page/reload/corruption/cancellation cases. The full browser run
also passed actual upload/analysis/evidence/review/revisit against the new API
(test 28), so this is not only mocked transport coverage. First full run exposed
a legacy fixture returning unrelated 200 data at the new overview URL; corrected
to an explicit legacy 404 and restarted. Full local suites subsequently passed: 73 browser tests and 273 Python tests
(16 skipped pending the Linux/provider prerequisites). [Source CI 37264475124](https://github.com/WhitefistEmperor/riskweave/actions/runs/37264475124)
and [source CI 37264478796](https://github.com/WhitefistEmperor/riskweave/actions/runs/37264478796)
passed all six checks on 134c67c: 289 Python tests, 73 production-browser tests,
containers, actual PostgreSQL inference/background delivery and encrypted restore
in both storage modes. Neither frontend job required a retry. Production inventory
is 440,712,884 bytes against 450 MB; actual hosted bundle remains unverified. Native encrypted tests may skip
without an installed age executable; CI exercises those plus actual PostgreSQL.

Loopback API now session 34961 / PID 54368, frontend session 20073, production
Next build. The API was idle with zero active analyses/open uploads before restart;
no migration or case erasure occurred. Generated 1,021-event smoke passed in
17.29s, preserving historical result SHA bb3977...; reviews and malformed422/
other-owner404 passed; only its own generated fixture was deleted.

Next: preserve this exact source and inspect newer CI after any changes. Measure
selected-section and hosted capacity; provision
live authentication, private PostgreSQL, workflow/cron, monitoring and off-host
backups after Vercel access is restored. Real-data model validation still requires
authorized exports and resolved labels. Full release gates below remain open.
Usage snapshot: 24% current-window remaining, 59% weekly remaining. This file is
already on GitHub; refresh it before remaining usage falls to 10%.

- New application source `799e75b6def2be3f190ca87d3f40cfde1b9bd5a9`, pushed.
  Adds owner-scoped candidate pages (1–100 items, stable ordinal ranges) and
  candidate/evidence section manifest/chunk endpoints. Indexed fragment delivery
  verifies containing source result chunks and never assembles the complete section;
  each raw read/chunk is at most 2 MB. Original bytes/hashes and old routes remain.
  Migration 0010 adds a page-range index without changing migration 0009.
  All 25 focused section/persistence/PostgreSQL compilation tests passed locally,
  including eight new cases across both storage modes and actual HTTP contracts.
  [Push CI 37261238329](https://github.com/WhitefistEmperor/riskweave/actions/runs/37261238329)
  and PR CI 37261242414 passed all six checks: 287 Python tests, 69 browser tests,
  containers and encrypted actual PostgreSQL restore in both storage modes.
  Push browser first failed rapid keyboard selection at 1024px; PR passed and one
  push failed-job retry passed. Trace shows no selected entity, but exact cause is
  unresolved. Retain/reproduce this timing signal; no assertion was loosened.
  Ignored diagnostic archive is work/section-transport-browser-diagnostics/.
  Production inventory is 440,704,096 bytes against 450 MB, not hosted bundle size.
  PostgreSQL encrypted restore drills now
  exercise paginated candidates and section fragments with whole reads disabled.
  See `docs/candidate-section-transport.md` for client reconstruction integrity gates.
  The console still assembles complete results; API completion does not close browser
  or hosted capacity. Candidate page count does not bound a single summary's bytes.
  Local preview was idle, its owned API was stopped, and a verified offline SQLite
  copy plus 34 object files was created at work/browser-before-0010-20261005/.
  This is a raw migration safeguard, not a manifest-format backup CLI snapshot.
  Explicit migration through 0010 preserved all original table row counts and run
  result checksum/reference fingerprints; SQLite integrity passed. API restarted
  session 84114 / PID 17628, loopback8000, trusted unchanged model and local jobs.
  Generated 1,021-event smoke completed/reviewed/deleted only its own fixture;
  historical result SHA bb3977... unchanged, malformed422/other-owner404, cleanupcomplete.
  Log work/section-transport-api.log. No live deployment or actual cases were erased.
  Earlier statements that the browser DB is 0008 describe historical state.

- New application source `ab475aeb93dc493e530ec087183199ed2aa52a14`, pushed.
  Migration 0009 adds immutable candidate/query/currency range metadata and an
  explicit index marker. New ring/evidence/investigator/review membership paths
  use verified targeted reads; original result bytes/checksums are preserved.
  Both storage modes passed 12 new tests on generated results with >2 MB selected
  evidence and unrelated large fields, with whole-object reads disabled. They cover
  owner denial, reviews, checksum corruption, missing rows, erasure, rollback,
  legacy maintenance and active-job refusal. All 34 focused section/review/transport
  checks plus the PostgreSQL migration compilation passed locally.
  First 6f8c578 CI passed browser/containers and 278 Python tests; its one failure
  was the persistence test's exact table list omitting result_sections. That
  expectation is corrected in ab475ae; all three local persistence tests passed.
  Corrected [push CI 37260356018](https://github.com/WhitefistEmperor/riskweave/actions/runs/37260356018)
  and PR CI 37260360209 passed all six checks: 279 Python tests, 69 browser tests,
  both containers, actual inference/background delivery and encrypted PostgreSQL
  restores with targeted candidate/review reads in both storage modes.
  Production inventory is 440,662,028 bytes against 450 MB, not hosted bundle size.
  The earlier Windows capacity baseline predates this indexing change; remeasure
  new persistence overhead alongside the remaining large-case contracts.
  PostgreSQL restore drill now verifies targeted reads and restored review membership
  with whole reads disabled. See `docs/targeted-result-sections.md` for maintenance.
  Existing local browser DB remains at 0008; do not start this source against it
  before stopping all writers, backing up and explicitly applying migration 0009.
  Selected evidence sections still assemble in memory; listing lacks pagination,
  individual evidence HTTP responses lack fragments and browser assembly is unchanged.
  No claim of hosted/worst-case capacity or whole large-case release completion.

- Documentation/audit head `3692d3d09a8c3709e761ef64a4e0a31b5d920cb6`
  passed all six push/PR checks (37259040665 / 37259044441). Application source
  remains e2926f4. The next independent implementation is targeted candidate and
  evidence reads, including review membership; see the release audit's confirmed
  gap. Current green checks do not prove large-result memory/response bounds.

- Current readiness fix `e2926f46588166323e40075bb90db9249031dd16`, pushed. Ruff and all 31 focused lifecycle,
  operational-limit and deletion checks passed locally. Local storage readiness
  now owns one write lock through its quota check, probe write/read and final
  unlink; a competing writer returns not-ready instead of raising an uncaught
  RuntimeError. The owned probe is removed even if its read fails. Existing data
  and the storage byte ceiling are preserved. Three new checks exercise real lock
  contention, an injected read failure while lock ownership is asserted, and a
  full store. [Push CI 37256671976](https://github.com/WhitefistEmperor/riskweave/actions/runs/37256671976)
  and PR CI 37256675191 passed all six checks without retries: 267 Python tests,
  69 browser tests, containers, encrypted PostgreSQL restore and actual SDK delivery.
  Production dependency/model inventory is 440,599,238 bytes, below 450 MB;
  this remains a packaging inventory rather than the hosted function size.
  Fresh scoped Vercel API recheck still returned 403, explicitly requiring
  reauthentication to sahilsinghkushwah10thb-9948s-projects. No release was created.
  This removes a concrete readiness lock-reacquisition race; it does not prove
  the original container deletion's exact cause or guarantee synchronous erasure.
  Durable pending deletion tasks still require the operator cleanup workflow.

- New encryption source `36bcc25413a7f71dfeed5056629288bc800b1c67`, pushed.
  Ruff and 15 actual native age 1.3.2 tests passed locally, using generated persisted
  payload/results with both SQLite storage modes. Wrong keys, ciphertext tampering,
  unsafe members and existing outputs are rejected. Root manifest is published last
  after complete authentication and validation; failed extraction stays private/incomplete.
  Linux CI installs only SHA-256-pinned official age executables and additionally wraps
  the existing PostgreSQL 17 two-storage-mode restore drills in encrypted round trips.
  [Push CI 37256000817](https://github.com/WhitefistEmperor/riskweave/actions/runs/37256000817)
  passed all three jobs: 264 Python tests, 69 browser tests and both containers,
  including encrypted actual PostgreSQL 17 restores in both storage modes.
  Production inventory is 440,596,478 bytes, below the 450 MB budget (not a hosted bundle).
  [PR CI 37256004159](https://github.com/WhitefistEmperor/riskweave/actions/runs/37256004159)
  also passed all three jobs after a single container retry. Its first attempt returned
  deletion storage_cleanup=pending with storage_cleanup_retry_pending, while the
  exact-source push container passed. The one failed-job retry passed.
  Preserve this initial failure: local storage uses a nonblocking write lock;
  contention can leave durable cleanup tasks requiring the operator cleanup CLI.
  Do not infer all deletion requests synchronously erase bytes or hide pending cleanup.
  See `docs/snapshot-encryption.md`. Keys, ciphertext, plaintext fixtures and binaries
  remain ignored/local; no live cases, model scores or deployment were changed.
  This completes a manual standard-encryption envelope, not scheduled off-host backup,
  key custody/rotation, provider configuration, secure erasure or hosted recovery.

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

Next independent code work: finish exact-source CI verification of the new paged
console and measure selected-section, summary and investigator capacity. Preserve small-case behavior and full
analyst functionality. Then remeasure browser/selected-section/indexing overhead and
verify actual hosted limits. Deployment/data blockers remain separate.

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
4. Apply migrations explicitly through 0010 and provision a live OIDC provider.
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
   whole-object verification until explicit indexing. The browser now assembles only selected sections when overview is available;
   legacy API fallback still assembles complete objects. Large legacy evidence, candidate and investigator replies still need
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
