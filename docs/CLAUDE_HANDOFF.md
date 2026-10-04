# RiskWeave continuation handoff

Updated 4 October 2026. This document is a continuation brief, not a claim that
the project is already deployed or validated on real financial data.

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
- Native Next.js 16.3.8 console, standalone non-root Docker build.
- Optional private database object storage, atomic global byte admission,
  checksummed reads, offline verified file import and backup/restore tooling.
- Request-mode global SQL execution claim, killable bounded subprocess,
  queue/execution deadlines, scoped recovery and fencing of late results.
- Private 2 MB upload parts, saved-part resume/discard/expiry, whole-file
  validation/SHA-256 and atomic artifact acceptance. Private result manifests
  and base64 fragments with fragment and complete-object integrity verification.
- Optional Python Vercel Workflow adapter with transactional delivery intent,
  30-second submission leases, bounded retries/backoff, monthly start admission,
  daily/hourly recovery, provider-status repair and no browser execution dependency.
  A changed model digest fails a queued run rather than changing its provenance.
  Erasure removes dispatch intent; stale steps cannot resurrect a case.
- Alembic head is `0006`; upgrades preserve populated cases/reviews/foreign keys.
- CI covers backend, native frontend and isolated PostgreSQL/container workflows.

Read these documents before redesigning anything:
`docs/production-progress.md`, `docs/vercel-deployment.md`,
`docs/request-execution.md`, `docs/background-delivery.md`,
`docs/bounded-transport.md`, and the existing security/model/backup documentation.

## Verification and model caveats

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
- The Vercel connector returned empty teams/403 for the owning workspace;
  Vercel CLI was not authenticated. Do not assume connector access has changed.
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
3. Complete the Python API's actual Vercel entry point/build configuration:
   supported Python runtime, trusted artifact/manifest packaging, writable `/tmp`
   scratch, generated authenticated Workflow queue functions, function duration,
   memory, bundle limits and routing. `pyproject.toml` registry metadata alone is
   not proof of a deployable API. Normal filesystem/scheduler defaults are unsafe
   for serverless; select database/request/managed-workflow mode explicitly.
4. Apply migrations explicitly through 0006 and provision a live OIDC provider.
   Align issuer/audience/scope/JWKS and registered exact HTTPS callbacks/logout.
   Add safe public-key rotation/retrieval; static verification keys are insufficient
   as a long-term operational rotation process. No public dev identity/demo in prod.
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
7. Benchmark actual deployment memory/latency/input bounds. Fragment endpoints
   currently read/hash entire results repeatedly; the browser assembles complete
   objects. Large legacy evidence, candidate and investigator replies still need
   bounds/capacity review. Verify subprocess support/termination in Python Functions.
8. Add external readiness/queue/error monitoring and alerts, scheduled encrypted
   backups, restore drills, rollback and operator runbooks. Define retention/holds
   and erasure across exports/snapshots/provider workflow histories. The hourly
   reconciler does not delete expired case data automatically.
9. Validate the detector on permissioned real data: ingestion mappings, temporal
   holdouts, leakage controls, calibration, threshold costs, subgroup/error analysis,
   distribution shift and documented operating limits. Real-data evaluation needs
   authorized data; never fabricate results to fill that gap.
10. Complete product gaps supported by actual usage: worklist review summaries,
    filtering/search, permissions/teams where required, accessible onboarding,
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
