# Investigation deletion and retention

Analysts can delete an owned investigation from its detail page. The confirmation
requires the exact saved name and the version of the case that was loaded. The API
checks ownership, name and `updated_at` again inside the database write transaction.
A new upload, run or analyst note makes an old confirmation fail with 409. The
browser preserves the typed name and requires a page reload before another attempt.
An inaccessible or already deleted case returns 404 without disclosing its owner.

Queued/running analyses and uploads prevent deletion. Both the case status and run
records are checked; a stale parent status cannot bypass an active job. Deletion
removes the case, artifacts, runs, analyst reviews and review history together.
The authenticated user account remains. There is no individual audit-note editing
or deletion endpoint; whole-case deletion removes the case's entire history.

## API

`DELETE /api/v1/investigations/{id}` takes:

```json
{"confirm_name":"Saved case name","expected_updated_at":"2026-10-03T12:00:00Z"}
```

Copy `updated_at` from the most recent authorized investigation response. A successful
response contains only `investigation_id`, `status: "deleted"` and
`storage_cleanup: "complete" | "pending"`. A missing response is not proof of failure:
check the investigation list. Repeating deletion of a removed case returns 404 and
does not recreate anything. The browser validates response scope before navigation.

## File cleanup and failure recovery

With `RINGSENTINEL_STORAGE_BACKEND=database`, private object bytes commit their
deletion in the same transaction as case metadata and review history. No file
cleanup task is required for new database objects. Old imported filesystem copies,
exports and snapshots need their own authorized erasure policy. The retryable
file-cleanup behavior below applies to the default local-storage backend.

Database erasure and a `storage_deletions` entry for every referenced object commit
in one transaction. File removal starts only after that commit. A transaction failure
leaves metadata and files intact. Storage failure leaves cleanup work in the database;
the removed case is immediately unavailable through the API.

Cleanup is idempotent: an already removed object is acknowledged safely. It refuses
to unlink any object still referenced by a live artifact or run. Corrupt shared
references block case deletion rather than destroying another case's files. The
storage backend validates opaque keys, confines paths to its configured directory,
rejects symlinks and serializes removal with byte-budget admission.

The single scheduler retries up to 100 cleanup tasks at startup and every minute
between analyses. Unattempted tasks run first, then least-recently attempted tasks,
so persistent failures cannot starve the rest of the queue. There is no distributed cleanup worker. If jobs are disabled or
cleanup is pending, an operator can run:

```sh
uv run --locked python -m ringsentinel.platform.deletion --limit 100
```

This processes only committed deletion tasks. Exit 0 means no tasks remain; exit 2
means cleanup is still pending; exit 1 means the operation could not be completed.
Repeat for larger queues. Private operator logs use fixed event names and never
include exception strings or case content. The queue records attempt count, time,
and a fixed error code (`STORAGE_UNAVAILABLE`, `UNSAFE_LOCATION`, `REFERENCED_OBJECT`).
Investigate persistent failures rather than ignoring them.

## Operator-controlled retention

Retention is disabled as an automatic deletion policy. Inspect the plan first:

```sh
uv run --locked python -m ringsentinel.platform.backup retention-report
```

`RINGSENTINEL_RETENTION_DAYS` determines the inactive age (default 90 days).
New review notes refresh case activity; idempotent retries do not. Eligibility excludes
active work and candidates whose saved disposition is Investigating or Escalated.
This is a workflow safeguard, not an organizational legal-hold system.

After selecting and approving the organization's retention period, an operator with
database/storage administration access can explicitly apply one bounded batch:

```sh
uv run --locked python -m ringsentinel.platform.backup retention-delete --confirm-delete-expired --limit 100
```

The operation rechecks inactivity and open work under the write lock for each case;
concurrent activity causes it to skip that case. It reports deleted cases, changed
cases skipped and remaining stored objects. It uses the same durable cleanup path.
No application startup or scheduler invocation applies the age policy implicitly.
Deployment scheduling and organization-specific holds still require configuration.

## Backups, exports and erasure scope

New offline backups refuse to start while any deletion cleanup is pending. Finish
cleanup first, then snapshot. A snapshot made after successful deletion contains no
metadata or referenced files for the removed case.

Existing snapshots, exports, infrastructure snapshots, storage replicas and previously
shared provider facts are separate copies. This operation is unlinking and relational
erasure, not secure physical-media wiping. Expire those copies under the organization's
policy. Restoring an older snapshot can restore a case deleted later; reapply authorized
deletions and retention before serving that restored database. A cross-snapshot erasure
ledger, encrypted scheduled backups and a deployed restore drill remain acceptance work.

## Migration

Stop writers, apply `ringsentinel-migrate`, then restart. Migration 0003 adds the cleanup
queue and preserves existing cases and review history. Readiness rejects older schema
revisions or missing queue tables. Migrations 0001 and 0002 remain unchanged.
