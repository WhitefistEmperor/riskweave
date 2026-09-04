# Phase 5C container/PostgreSQL gate

Measured on 2026-09-04: Docker, Podman, psql, pg_dump and pg_restore are unavailable on PATH;
standard Windows Docker/PostgreSQL installation locations are also absent. No runtime was installed,
no VM was started, no public service was deployed. Image builds, Compose runtime validation, live
PostgreSQL migrations/locks/backup/restore and persisted container restart remain **unverified**.

Locally completed: actual `0001` migration SQL compilation for PostgreSQL, ORM PostgreSQL DDL
compilation, foreign keys/timezone/active-slot constraint assertions, and standard pg_dump/pg_restore
argument/environment tests (explicitly mocked subprocess, not live PostgreSQL). SQLite actual
migrations, child execution, restart, quotas, locks, owner isolation and backup/restore are separate
real integration tests. Existing migration revision is untouched.

Compose remains a **loopback-only development-identity verification stack**, not production auth.
API/frontend now drop Linux capabilities, prohibit privilege gain, bound process count and rotate
container logs. Frontend image validates its explicit proxy target at production build time. These
recipe changes require the following real runtime checks before deployment approval.

## Exact remaining local-stack commands (Docker-capable host)

Supply a URL-safe throwaway database password in `RINGSENTINEL_DB_PASSWORD` through a private shell.
Do not print `docker compose config` with values or inspect process environments in shared logs.

```text
docker compose config --quiet
docker compose build
docker compose up --wait --wait-timeout 180
docker compose run --rm migrate
curl --fail http://127.0.0.1:8000/api/v1/health
curl --fail http://127.0.0.1:8000/api/v1/ready
uv run --locked --extra dev python scripts/smoke_platform.py --base-url http://127.0.0.1:8000
docker compose restart backend
docker compose up --wait --wait-timeout 180
uv run --locked --extra dev python scripts/smoke_platform.py --base-url http://127.0.0.1:8000 --reopen-run RUN_ID_FROM_SMOKE
```

For an empty-database migration check, use a new isolated Compose project/volumes, not existing data.
The first `up` runs migrations from empty automatically; the repeated migrate must remain idempotent.
Verify result checksum and saved investigation after restart. Test second-backend startup rejection
and run PostgreSQL backup/restore using `docs/backup-restore.md`, against separate throwaway targets.
Stop with `docker compose stop`; do not remove volumes to simulate restart.

Before later staging: execute the same product smoke with real gateway-signed tokens, HTTPS,
production config/demo disabled, private backend access and owner isolation. Gateway session/CSRF,
network allowlists, TLS trust, health routing, body/rate/connection limits and logging must be tested
on that chosen platform. No such integration or staging deployment was done in Phase 5C.
