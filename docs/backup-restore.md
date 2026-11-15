# Backup and offline restore

Use a private operator shell with existing environment configuration. Snapshots contain sensitive
data: restrict filesystem permissions, encrypt off-host copies with standard platform tooling,
keep encryption keys separately, and test restoration regularly. No encryption key or DB password
belongs in Git or a command argument. The snapshot command produces plaintext. The separate [age envelope tool](snapshot-encryption.md)
adds standard encryption; PITR and hosted scheduling remain unimplemented.

## Default offline backup

For database object storage, case bytes are inside the database backup. Manifests
record `storage_backend`; restore requires the same backend (older manifests mean
local storage). The snapshot mutation lock also blocks request-mode claims/writes.
All replicas must still be stopped. Recover expired request-mode runs through
authorized status reads rather than starting a local scheduler on that database.
See [request execution and import](request-execution.md).

1. Block new traffic at the gateway. Stop **all** API replicas, including jobs-disabled writers.
   Graceful shutdown terminates analysis; queued runs remain queued. Inspect safe shutdown logs.
   If recovering an ungraceful stop, start exactly one backend to mark interrupted runs failed,
   then stop it normally. Never delete lock files to force access.
2. Keep PostgreSQL running. Supply the DB URL/storage root through the environment, and install
   `pg_dump`/`pg_restore` matching the PostgreSQL server major version (17 in Compose).
3. Run from the repository root, choosing a new private directory outside live storage:

   ```text
   uv run --locked python -m ringsentinel.platform.backup backup --directory work/backups/snapshot-001 --writers-stopped
   ```

The explicit flag is an operator acknowledgement, not automatic traffic draining. Executor and
child locks detect an active supported scheduler/child, but cannot detect arbitrary external SQL
writers or an operator deliberately running an additional jobs-disabled API. Keep every writer
stopped until completion. A PostgreSQL database dump is internally consistent; it is not atomically
consistent with the filesystem unless application writes are quiesced.

The tool checks referenced input/result hashes, uses `pg_dump --format=custom --no-owner --no-acl`
for PostgreSQL (SQLite's backup API locally), copies opaque JSON objects including possible orphans,
and writes `manifest.json` last with sizes and SHA-256 hashes. Database credentials are passed through
private process environment, never argv or logs. Missing manifest means incomplete: do not restore.
No existing snapshot is overwritten and failed snapshot data is left for operator inspection.

## Opt-in online PostgreSQL backup

With `RINGSENTINEL_STORAGE_BACKEND=database` and PostgreSQL only, use:

```text
uv run --locked python -m ringsentinel.platform.backup backup --directory work/backups/online-001 --online-database
```

Supply the existing private database configuration through the environment. Install matching
PostgreSQL clients and choose a new private destination outside live storage. Do not combine
this flag with `--writers-stopped` or use it for restore. SQLite and filesystem storage reject it
before connecting or creating a destination.

The exporter holds a read-only REPEATABLE READ transaction. It checks the current migration
and referenced input/completed-result hashes using database object reads in that same transaction,
exports its PostgreSQL snapshot and passes it to `pg_dump --snapshot`. The exporting transaction
stays open until the dump completes. Ordinary case/object writes may continue; all metadata and
object bytes in the dump reflect the same database view. Coordinate schema migrations separately.
See PostgreSQL's [snapshot lifetime and synchronization](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-SNAPSHOT-SYNCHRONIZATION)
and [pg_dump snapshot option](https://www.postgresql.org/docs/17/app-pgdump.html).

The manifest records `consistency=postgres-exported-snapshot` and is written last. `created_at`
is completion time, not a measured recovery point. Integrity verification reads each referenced
object in full; this is not a bounded-memory or hosted-capacity claim. Failed dumps leave no
completion manifest. Existing destinations are never overwritten. Encryption/off-host transfer
remain separate steps, and no schedule or hosted recovery objective is established by this CLI.

Online backups can contain in-flight runs, upload sessions, leases and dispatch rows. Restore
requires stopped writers and a new empty target, followed by expiry/lease/deadline reconciliation
for the configured execution mode. Do not blindly resume old external workflow deliveries or
claim exactly-once recovery. Review erasures/retention that committed after the snapshot before
cutover: an older snapshot can contain cases removed from the current database.

## Restore order

1. Keep traffic/API stopped. Provision a **new, empty** PostgreSQL database and a **nonexistent**
   artifact directory. Point environment variables at these throwaway/replacement targets, never
   the live database. Use the same application revision and database major version first.
2. Run:

   ```text
   uv run --locked python -m ringsentinel.platform.backup restore --directory work/backups/snapshot-001 --writers-stopped
   uv run --locked ringsentinel-migrate
   ```

All manifest paths and hashes are verified before target writes. Objects are restored first, then
metadata via `pg_restore --single-transaction --exit-on-error --no-owner --no-acl`; referenced input
and result hashes are checked again. Restoring a snapshot is trusted-operator work: a checksummed
snapshot is not an authenticated signature and must come from a trusted backup repository. Do not
restore attacker-supplied SQL dumps. Existing databases/storage are never overwritten. Failure leaves
partial new targets untouched; investigate them and retry into other new targets, not the originals.
3. Start one backend with new configuration. Check `/api/v1/health`, `/api/v1/ready`, owner isolation,
   saved investigations and completed result hashes. Queued work can resume when jobs are enabled.
   Only after verification may an operator separately authorize cutover. No cutover was done here.

PostgreSQL roles, passwords, TLS certificates, auth public keys, environment configuration and optional
provider credentials are intentionally not in the database snapshot. Back those up separately through
the deployment secret/configuration system. Determine RPO/RTO and backup retention before staging.

## Retention review (read-only)

```text
uv run --locked python -m ringsentinel.platform.backup retention-report
```

Lists idle investigations older than `RINGSENTINEL_RETENTION_DAYS` (default 90) by updated timestamp.
No deletion occurs. A reviewed deletion/legal-hold/privacy policy is still required; changing this
setting does not erase data. Storage quotas include orphan objects, deliberately favoring safety.

## Measured verification

SQLite round-trip tests restored actual generated input, completed result, owner associations,
checksums and migration state into a new database/storage directory. Tests reject active executor,
missing acknowledgement, overwrite, checksum corruption and traversal without damaging source data.
The test result payload is explicitly a small lifecycle fixture, not a new detector benchmark.
PostgreSQL executable paths are **not live tested on this Windows host**: Docker,
Podman, psql, pg_dump and pg_restore are absent. Linux CI now runs the actual
snapshot and restore code against PostgreSQL 17 with matching clients in ephemeral
containers, for both local and database object storage. The drill creates unique
test databases under a fixed loopback-only CI role and removes only those databases.
It verifies input bytes, result checksum, owner isolation, repeated migration and
existing-target rejection. Consult the exact source commit's backend CI result
before claiming that drill passed. Its small result is a generated lifecycle
fixture, not a new detector evaluation or a hosted production restore drill.

The online PostgreSQL control commits case/object erasure and a new case/upload through another
connection after snapshot export but before `pg_dump`. The fresh restored database must retain
the original case, exact input/result bytes and owner isolation, while the live source contains
only the new case. It is skipped on this Windows host; exact-source Linux CI is required.

Reference: [PostgreSQL SQL dump consistency](https://www.postgresql.org/docs/17/backup-dump.html).
