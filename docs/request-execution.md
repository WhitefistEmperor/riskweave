# Durable objects and request execution

Migration `0004` adds private database objects and run execution deadlines. The
default remains the single local scheduler and filesystem storage. Request mode
is an explicitly selected deployment foundation; it is not yet a complete Vercel
release or a durable background dispatcher.

## Storage and consistency

`RINGSENTINEL_STORAGE_BACKEND=database` stores uploaded inputs and serialized
results as PostgreSQL `bytea` (SQLite is supported for isolated tests). Opaque
keys are preserved and never exposed as public object URLs. Existing owner checks
authorize artifact/result access. Reads verify recorded size and SHA-256.

Database objects, artifact/run metadata and global byte admission commit in the
same SQL transaction. A failed metadata write rolls back its bytes. Whole-case
deletion removes these bytes with metadata and review history in one transaction.
All database objects, including unreferenced objects, count against the budget.
This avoids relying on a function instance's ephemeral filesystem for case data.
The database remains private; operators still need TLS, restricted credentials,
encrypted backups and a verified provider allowance. Object bytes also consume
database storage, transfer and backup capacity; the application budget is not a
provider billing cap.

## Execution configuration

Set `RINGSENTINEL_EXECUTION_MODE=request`, database storage and an analysis timeout
of at most 240 seconds. Production additionally requires PostgreSQL, JWT
authentication, enabled jobs, a build-owned model with pinned SHA-256 and an
explicit `RINGSENTINEL_STORAGE_LIMIT_BYTES`. Existing production origin/host,
public-JWKS, issuer, audience and scope requirements still apply. Configure
`RINGSENTINEL_STORAGE_ROOT` as disposable scratch, such as `/tmp/riskweave`;
it must not contain the sole copy of case data.

An owner calls `POST /api/v1/runs/{run_id}/execute` for a run already queued by
the normal idempotent start endpoint. Claims serialize across database instances
and allow one running analysis globally. Busy capacity returns the same queued
run. Repeating execution of a completed run returns that persisted outcome.
Cross-owner attempts return 404 before claim or execution. A bounded subprocess
performs inference using the trusted artifact, and the existing watchdog ends
overdue work. No scheduler starts from the request-mode ASGI lifespan.

A queued run expires after 24 hours. Claimed work has the analysis timeout plus
20 seconds for cleanup/persistence. Expired work becomes a safe failed outcome
and releases its capacity slot; late completion cannot publish bytes. Cold starts
do not fail healthy invocations. Owner case/worklist/run reads recover expired
work within their scope; execution also recovers a bounded batch globally to free
capacity. An explicit new start/idempotency key is required to retry failed work.

The console dispatches the same queued run while polling. **Closing the console
before dispatch can leave work queued until the case is reopened or expires.**
A durable dispatcher and retry scheduling remain release gates. Request mode
alone does not promise completion after every browser or network interruption.

Next.js's self-hosted rewrite timeout is bounded at 280 seconds, above the worker
deadline. Vercel's own routing/duration limits require separate hosted verification.
The existing 25 MB upload and 100 MB result budgets are preserved. Authenticated
[fragment transport](bounded-transport.md) supports large uploads and request-mode
result delivery below Vercel's 4.5 MB request/response ceiling. Other large evidence
and investigator replies, hosted routing and transport capacity still need verification.
Model bundle size, memory and worst-case latency must also be measured there.

## Existing filesystem cases

Stop all writers and finish/recover active runs and pending deletion first. Take
a verified offline backup using the existing local-storage configuration. Then
select database storage and run, with the same database and source storage root:

```sh
uv run --locked python -m ringsentinel.platform.database_storage --confirm-writers-stopped
```

The importer checks all referenced inputs/completed results, preserves their keys,
verifies checksums/sizes, enforces the byte budget and commits the copy atomically.
Retries verify existing bytes and copy only missing objects. Active work, pending
deletion, tampered files or insufficient quota reject the import. Database-storage
readiness refuses missing referenced objects, so changing the setting alone does
not silently create a working deployment.

Source files are retained; import does not remove old copies or snapshots. Verify
the imported cases and new backup before applying an authorized source-copy
retention/erasure policy. Deleting a database-backed case does not erase old source
files, exports or older snapshots. Cross-snapshot erasure reconciliation remains
necessary.

## Backup and verification

Offline snapshots hold the database mutation lock across verification and copying.
With database storage, object bytes travel inside the database backup rather than
a scratch directory. The manifest records the selected storage backend, and
restore requires a matching target. Legacy manifests default to local storage.
Restore uses a new empty target and verifies referenced bytes afterward.

`compose.request.yml` overrides the local-only stack for real PostgreSQL verification:

```sh
docker compose -f compose.yaml -f compose.request.yml up --wait backend
uv run --locked --extra dev python scripts/smoke_platform.py --request-execution --delete-created
```

This uses isolated development identity. It verifies persisted inference, review,
repeat reads and deletion; it is not a substitute for hosted JWT/HTTPS, provider
quotas, hosted transport capacity, background delivery or real-payment model evaluation.
