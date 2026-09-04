# Offline backup and restore

Use a private operator shell with existing environment configuration. Snapshots contain sensitive
data: restrict filesystem permissions, encrypt off-host copies with standard platform tooling,
keep encryption keys separately, and test restoration regularly. No encryption key or DB password
belongs in Git or a command argument. This tool does not implement encryption, PITR or scheduling.

## Consistency and backup

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
PostgreSQL executable paths are implemented but **not live tested on this host**: Docker, Podman,
psql, pg_dump and pg_restore are absent. Do not treat the SQLite test as PostgreSQL verification.

Reference: [PostgreSQL SQL dump consistency](https://www.postgresql.org/docs/17/backup-dump.html).
