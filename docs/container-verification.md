# Local production-like containers and CI

## Scope

The root Dockerfiles prepare two non-root runtime images: a locked-uv Python
3.13 backend and the existing Node 24.19.0/Vinext production frontend. The
backend wheel installation includes migrations and the frozen Phase 3 reference
artifact. It runs Uvicorn without a reloader, with **one worker** and a 20-second
graceful shutdown budget. One worker owns the local scheduler and its single
killable analysis subprocess; increasing API workers would violate that executor
assumption. Compose gives the process 30 seconds to stop.

`compose.yaml` adds PostgreSQL 17, a one-shot explicit migration service, and
persistent named database/artifact volumes. The database has no host port.
Backend and frontend ports bind only to `127.0.0.1`. Nothing in these files
creates a public deployment, DNS record, cloud account, or paid-provider call.

The backend image defaults to production settings with authentication disabled
and the demo disabled: protected APIs fail closed until a real principal provider
exists. Compose explicitly opts into the **local development identity** and demo.
It is a production-like process/storage topology, not production authentication.

The frontend uses `vinext start`, not Vite's development server. Its rewrite
target is a non-secret **build-time** `RINGSENTINEL_API_PROXY_TARGET` argument,
set to `http://backend:8000` inside Compose. Rebuild the frontend to change this
same-origin proxy destination. Secrets must never be passed as frontend build
arguments. The runtime image retains the tested Vinext CLI dependency closure;
tool peers have not been assumed safe to prune.

## Commands (require an installed, running Docker engine)

Set `RINGSENTINEL_DB_PASSWORD` in the process environment to a local throwaway
credential containing URL-safe characters. Do not reuse a real credential and do
not commit it. Arbitrary reserved URL characters require percent encoding in a
database connection URL; this minimal Compose template deliberately uses a
URL-safe local credential instead.

```powershell
$env:RINGSENTINEL_DB_PASSWORD = 'replace-with-a-local-url-safe-value'
docker compose config --quiet
docker compose build
docker compose up --wait --wait-timeout 180
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/ready
```

Open the frontend at `http://127.0.0.1:5173`. On a later schema update, stop the
API before explicitly applying migrations; do not let application startup create
tables implicitly. A first `compose up` runs the migration service before the API
starts. `docker compose down` stops this stack while preserving its named volumes.
Do not add `--volumes` unless deliberately deleting the persisted investigations.

For an isolated migration command against the configured Compose database:

```text
docker compose run --rm migrate
```

`.dockerignore` excludes Git metadata, environment files, local keys, virtual
environments, node_modules, datasets, scratch data, test captures, caches and
existing build output. Installs use `uv.lock`/`npm ci`. Runtime base tags are
version-family pinned, not immutable digest pinned; reviewed digest pinning and
OS-image security scanning remain explicit Phase 5C work.

## Actual local verification on 2026-09-04

| Check | Actual result |
| --- | --- |
| `Get-Command docker,podman,wsl` | Docker and Podman absent; Windows WSL launcher present. |
| `wsl --list --quiet` | Windows reports that WSL is not installed. |
| Standard Docker/Podman installation paths and services | No matching runtime found. |
| Compose/workflow YAML parsing with isolated PyYAML | Both documents parsed successfully. |
| Isolated `dockerfile-parse` syntax parsing | Backend 21 instructions and frontend 23 instructions parsed. This is not a Docker build. |
| Static topology assertions | Four Compose services, three CI jobs, loopback-only published ports, no published PostgreSQL port, and migration-before-backend dependency passed. |
| Docker image builds | **Not run: no container engine available.** |
| Local Compose health/readiness and investigation smoke | **Not run: no container engine available.** |

No daemon, WSL distribution, VM, or system service was installed as a workaround.
YAML parsing is not container execution and is not reported as a successful
image build. The user's container-build completion criterion remains unverified
on this machine until Docker is available and the commands above are executed.

## CI

`.github/workflows/ci.yml` defines push/pull-request checks with read-only
repository permissions, no deployment job and no application/provider secrets:

- Backend: locked install, Ruff, all Python tests, migration of a fresh SQLite
  database twice to verify repeatability, and wheel/sdist build.
- Frontend: lockfile install, lint, TypeScript, production build, Chromium install,
  real local API and production frontend, and the browser suite.
- Containers: Compose validation, both image builds, a local PostgreSQL stack,
  health/readiness/frontend checks, and `scripts/smoke_platform.py` against the
  real container API; the ephemeral CI stack is stopped after.

These workflows are configured, not claimed to have run on GitHub from this
local task. Build/test outcomes must be read from an actual CI run. Log artifacts
are kept only on test failure for seven days; fixtures use synthetic data and
the deterministic investigator, never customer datasets or API keys.
