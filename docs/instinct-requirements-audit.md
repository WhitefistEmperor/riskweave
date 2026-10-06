# Original plan audit, 6 October 2026

The user-linked [RiskWeave: build and ship](https://files.instinct.com/file-01M3Z91EVRMY9WNSX7G8R51ARE)
is now readable through the supported in-app browser. Its26 items are mapped below.
Reading is complete; implementation acceptance remains mixed. Page checkboxes
were not changed. No private lease links or account identifiers are saved. These
IDs refer to the source plan, not the user's separate six remaining-work steps.

| Source item | Current repository evidence / remaining work |
|---|---|
| 1.1 Foundation inspection | Settings, migrations, worker and both stores inspected. Deterministic investigator preserved. |
| 1.2 Compose services | API/PostgreSQL/frontend, health checks, volumes and secret-free example exist. Redis/evidence cache absent. |
| 1.3 PostgreSQL migrations | CI explicitly migrates fresh PostgreSQL; Compose waits for one-shot migration before API startup. |
| 1.4 Investigation smoke | Container CI runs persisted analysis, checks ownership and hashes; browser workflows exercise evidence/investigator/reload. Hosted repeat open. |
| 1.5 Restart persistence | Durable objects and restore verified; retain a case across an explicit container restart and inspect it before cleanup. |
| 2.1 Cache target | No backend immutable evidence/answer cache found. Feature-density and JWKS caches do not close this gap. |
| 2.2 Cache scoping | Owner/result/query/version keys, TTL and lifecycle behavior for that evidence cache remain to implement. |
| 2.3 Cache resilience | Hits/expiry/concurrent owner checks and Redis outage fallback remain to implement and measure. |
| 2.4 Durable queue | Actual Vercel Workflow SDK locally exercised instead of adding another queue library. Hosted generated routes/delivery open. |
| 2.5 Job recovery | SQL dispatch, leases, retries, deadlines, model fencing and reconciliation have local/CI controls. Hosted recovery unverified. |
| 2.6 Shared durable bytes | Request mode uses PostgreSQL objects with atomic integrity/ownership. Hosted database remains unavailable. |
| 3.1 Hosting selection | User selected free Vercel; workspace returns403. Account allowances/database/identity still need verification. |
| 3.2 Backend deployment | Source packaging exists; no verified live backend/Workflow/database release. |
| 3.3 Frontend deployment | Native Next.js replaces old Vinext. Hosted issuer/proxy/origin/build checks still depend on access. |
| 3.4 Demo safeguards | Bounded uploads, quotas, rate limits, production authentication admission and synthetic controls exist; hosted configuration unverified. |
| 3.5 HTTPS acceptance | Requires deployed URL, identity and durable resources. Local/CI checks are insufficient. |
| 3.6 Demo publication | Live link, hosted cold/warm measurements and release walkthrough remain open. |
| 4.1 Optional agent flag | Deterministic mode and opt-in fact selection exist. A new agent loop remains deferred until infrastructure is stable. |
| 4.2 Optional read tools | Owner-scoped evidence/query services exist; no new bounded multi-tool agent loop implemented. |
| 4.3 Optional agent budgets | Existing provider has timeout/bounded selections. Agent steps/token/spend budgets remain future work. |
| 4.4 Optional citations | Current investigator validates selected fact IDs and renders computed statements; future tool traces need verification. |
| 4.5 Optional agent evaluation | Current deterministic/fact-selector controls exist. Multi-step-agent evaluation deferred with optional loop. |
| 5.1 Reproducible documentation | Compose/migration/request/SDK instructions exist. Container documentation corrected to match standalone Next.js image. |
| 5.2 Evidence-backed claims | PostgreSQL/SDK/recovery have pinned receipts; hosted/cache/agent-loop claims remain unverified. |
| 5.3 Release materials | Local screenshots/benchmarks exist; live demo and hosted walkthrough absent. |
| 5.4 Retrieval terminology | README describes cited computed facts. No vector-retrieval claim or embedding dependency introduced. |

Next independent source-plan work is an owner-scoped immutable evidence cache with
bounded entries, failure fallback and measured hits. Keep database bytes authoritative,
preserve ownership checks on every hit, and verify erase/invalidation. Redis must
not become required for inference or a hidden paid resource. Review existing
response/fragment budgets before adding it.

Capacity and observed-data approval remain separate gates in
[RELEASE_GATES.md](RELEASE_GATES.md). Reading does not supply payment records,
deployment credentials or proof of a finished release.
