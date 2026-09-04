# RiskWeave local quick start

The public product was previously named RingSentinel. Commands and internal configuration
still use `ringsentinel` / `RINGSENTINEL_*`; do not rename them when following this guide.

This runs the existing application on your own computer. It does not deploy anything.
Use a repository checkout, Python 3.11+ with uv, and Node.js 22.13+ with npm.
The final local verification used Python 3.14.6 and Node.js 24.19.
The existing CI workflow targets Python 3.13; remote CI was not run in this pass.

## 1. Backend — repository root

```sh
uv sync --locked --extra dev
uv run --locked ringsentinel-migrate
uv run --locked ringsentinel-api
```

Keep this terminal open. Defaults: http://127.0.0.1:8000, SQLite
`work/ringsentinel.db`, filesystem objects `work/storage`, one executor, local
development identity, demo enabled, deterministic investigator. Migration is repeatable.
`uv sync` creates the virtual environment; activating it manually is unnecessary.

No `.env` file is required or auto-loaded. Existing `RINGSENTINEL_*` shell variables
override defaults. See the root [configuration template](../.env.example).
Never commit credentials or reuse development identity for a public service.

## 2. Frontend — a second terminal

From the repository root:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173/investigations. The proxy sends `/api` requests to the backend.
Development API docs: http://127.0.0.1:8000/docs. Readiness: http://127.0.0.1:8000/api/v1/ready.

## 3. Sample upload — a third terminal at the root

```sh
uv run --locked python scripts/make_upload_sample.py --output work/sample.json --transactions 1000 --seed 105
```

The generator validates the bundle before saving. This seed/configuration produces
2,824 entities and 1,021 events (payments plus refunds). This small walkthrough sample
is not the five-seed, 5,000-payment-per-seed benchmark. File creation is exclusive:
if the file exists, reuse it or choose another filename; it is not overwritten.

1. Create an investigation with a clear name, such as “Shared infrastructure review.”
2. Select `work/sample.json` and click **Upload dataset**.
3. Click **Start analysis**; wait for **Completed** (cold analysis can take tens of seconds).
4. Review the ranked queue and open a candidate. Inspect Network, Evidence, and Timeline.
5. Open Investigator, ask a question, and follow a citation back to its source evidence.
6. Return to Investigations and reopen the saved run.

The upload must be a complete versioned DatasetBundle JSON, not CSV, JSONL, or an individual
table. The default upload limit is 25,000,000 bytes. Labels in a synthetic input are not used
to score that upload or construct its evidence. See [data model](data-model.md).

## 4. Tests and build

Root:

```sh
uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check .
```

In `frontend`, with both servers running:

```sh
npx playwright install chromium
npm test
npm run lint
npm run typecheck
npm run build
```

On Linux, Playwright may also need system libraries: `npx playwright install --with-deps chromium`.
The frontend suite expects demo access and `RINGSENTINEL_LLM_PROVIDER=deterministic`, the default.
It creates real local test investigations and also uses explicitly labeled UI transport fixtures.
Do not run it against a deployed or shared service.

For an isolated test or presentation workspace, set a **new** database/storage pair before
running both migration and API commands. Keep the same values for both commands. PowerShell:

```powershell
$env:RINGSENTINEL_DATABASE_URL='sqlite:///./work/presentation.db'
$env:RINGSENTINEL_STORAGE_ROOT='work/presentation-storage'
uv run --locked ringsentinel-migrate
uv run --locked ringsentinel-api
```

Bash/zsh equivalent:

```sh
export RINGSENTINEL_DATABASE_URL=sqlite:///./work/presentation.db
export RINGSENTINEL_STORAGE_ROOT=work/presentation-storage
uv run --locked ringsentinel-migrate
uv run --locked ringsentinel-api
```

Stop the existing backend with Ctrl+C first; never launch a second executor on its occupied port.
Changing this pair selects another workspace and does not delete existing investigations.

## Optional: stable local production-build preview

Stop the frontend dev server with Ctrl+C. In its terminal, inside `frontend`, use:

```sh
npm run build
npm start
```

This serves compiled output on http://127.0.0.1:5173, still against the local backend.
It is not production authentication or deployment approval.

To exercise the frontend's explicit production configuration guards as verified in Phase 6,
set these **frontend-terminal-only** variables before build and start. PowerShell:

```powershell
$env:RINGSENTINEL_ENVIRONMENT='production'
$env:RINGSENTINEL_API_PROXY_TARGET='http://127.0.0.1:8000'
npm run build
npm start
```

Bash/zsh:

```sh
export RINGSENTINEL_ENVIRONMENT=production
export RINGSENTINEL_API_PROXY_TARGET=http://127.0.0.1:8000
npm run build
npm start
```

Keep `NEXT_PUBLIC_RINGSENTINEL_API_BASE_URL` unset/empty for this same-origin mode. Do not
set production mode in the backend quick-start terminal: real deployment requires the
separately configured identity gateway and [unverified infrastructure gates](phase5c-final.md).

## Troubleshooting

- **Backend unavailable:** check readiness and that the API terminal is running on port 8000.
- **Port occupied:** reuse or stop the known local server; do not start another copy.
- **Schema/storage errors:** run migrations using the same environment and working directory
  as the API; confirm the selected local storage is writable.
- **No saved cases:** confirm the same database, storage root, and identity are in use.
- **Sample already exists:** reuse the file or change `--output`; no cleanup is necessary.
- **Investigator has no LLM:** expected by default. Computed, cited statements work without a key.
- **Replay cold start:** the separate `/demo` route may need 20–40 seconds to reproduce its fold.

See [the demo script](../DEMO_SCRIPT.md) for the concise reviewer walkthrough.
