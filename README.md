# RingSentinel

Temporal network intelligence for coordinated payment abuse.

RingSentinel is a working local analyst console for finding coordinated payment abuse that individual
transaction models can miss. It combines causal transaction, infrastructure, temporal, and graph
features, groups suspicious events into candidate rings, and exposes computed evidence to analysts.
The Phase 4 application includes FastAPI, a React/TypeScript dashboard, chronological simulation,
interactive network exploration, and an evidence-grounded investigator. **No GNN is used.**

The key insight: a payment can look ordinary alone but suspicious in its network context. Sharing alone
is also insufficient: legitimate families, offices, and hostels are explicit benchmark hard negatives.

## Run the analyst demo

Requirements: Python 3.11+, uv, Node 22.13+ (tested with Node 24.19), npm.
Run from this repository checkout. First setup needs internet for dependencies and fonts.

Terminal 1, repository root:

```powershell
uv sync --extra dev
uv run ringsentinel-api
```

Terminal 2:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. API docs: http://127.0.0.1:8000/docs.
Allow roughly 20–40 seconds for the first data request to reproduce the held-out seed-105 fold.
Use localhost only; this is not a hardened public deployment. Ctrl+C stops each terminal.
Stop the backend before changing Python package metadata/installing: Windows locks running launchers.

For a local production-build preview, stop the frontend dev server and run `npm run build`, then
`npm start` from `frontend`. Both modes forward `/api` to the local Python process.
No generated dataset, database, paid account, or LLM key is required.

Start replay, watch the first focus candidate appear, open Ring Explorer, inspect its graph/timeline,
ask “Why was this ring flagged?”, then visit Benchmark and Hard negatives. Follow the
[3–5 minute demo script](docs/demo-flow.md). Replay speed compresses waiting, not event timestamps.
The first live candidate is an observed-prefix snapshot; the sidebar Explorer is retrospective.

## Measured synthetic benchmark

Post-hardening Phase 3 means over five held-out ecosystems; unchanged in Phase 4:

| Model | PR-AUC | Precision | Recall | F1 | Event FPR | Ring detection |
|---|---:|---:|---:|---:|---:|---:|
| Transaction-only HGB | 0.199 | 0.627 | 0.154 | 0.243 | 0.55% | 30% |
| Graph heuristic | 0.321 | 0.331 | 0.287 | 0.307 | 2.75% | 28% |
| Network-aware HGB | 0.971 | 0.964 | 0.939 | 0.951 | 0.17% | 100% |

Exposure mean relative error: **8.14%**; aggregate underestimation: **4.44%** over 50 matched rings.
Detection recall does not establish valuation accuracy. Expected-loss rates are synthetic assumptions,
and scores are not calibrated probabilities. The eight-minute seed-105 example is not average latency:
the benchmark mean early-warning delay is about 20.95 hours. An earlier isolated threshold alert is
explicitly disclosed in the compact replay.

Validated on synthetic ecosystems; **not a production fraud-rate claim**. Distribution shift is unknown.
Merchant-collusion held-out PR-AUC varies (0.803 ± 0.143). Production needs retraining and monitoring.
Full results, standard deviations, ablations, and before/after hardening are preserved in
[Phase 3 results](results/phase3/phase3_summary.md) and [methodology](docs/benchmark-methodology.md).

## Investigator trust boundary

The question selects controlled evidence queries. The investigator never classifies fraud, invents
missing evidence, or changes the detector. Default mode is deterministic, with cited observations and
inspectable source data. Optional OpenAI extractive summarization selects/orders computed facts; it
cannot introduce free-form claims. Errors or invalid selections fall back safely. Configure server-side
environment variables from `.env.example` only if desired; `.env` is not auto-loaded.
See [investigator design](docs/investigator-design.md). Live paid-provider verification is not claimed.

## Screenshots

Browser-generated screenshots are in [docs/screenshots](docs/screenshots). Repeatable UI tests also
write current captures to ignored `outputs/phase4-*.png`.

![RingSentinel overview](docs/screenshots/phase4-overview.png)

## Checks

```powershell
uv run pytest -q
uv run ruff check .
uv build
cd frontend
npm run lint
npm run typecheck
npm run build
npx playwright install chromium
npm test
```

Browser tests require both servers running and use actual API data, not mocked benchmark responses.
The optional WebMCP contract is tested with an emulated registry; native browser support is not assumed.
Bundled shadcn catalog lint findings are excluded from application lint; all TypeScript is typechecked.
The pinned Sites/Vinext scaffold has npm audit findings (8 high, 2 moderate, 1 low at final audit) and a
large-chunk build warning. Keep it local; dependency security upgrades are required before deployment.

## Repository map

```text
src/ringsentinel/  generation, schemas, causal features, models, evaluation
  api/            FastAPI + deterministic held-out demo runtime
  investigation/  read-only evidence + constrained investigator providers
  simulation/     chronological candidate replay
frontend/         React/TypeScript operations console + browser tests
tests/            schema, leakage, benchmark, evidence, replay, API/provider tests
results/phase3/   preserved measured validation artifacts
docs/             architecture, methodology, evidence contract, demo script
```

See [architecture](docs/architecture.md) and [snapshot evidence contract](docs/evidence-ui.md).

## Synthetic data and experiment CLI

```powershell
uv sync --extra dev
uv run ringsentinel-generate --seed 42 --transactions 1000 --output data/generated/demo
uv run pytest
```

Equivalent module invocation:

```powershell
uv run python -m ringsentinel.generate --seed 42 --transactions 1000
```

Run the measured five-seed benchmark:

```powershell
uv run python -m ringsentinel.experiments.run --transactions 5000
```

Measured fold, scenario, hard-negative, candidate, exposure, threshold, and runtime outputs are written
to `results/phase2/`.

Run the Phase 3 validation suite:

```powershell
uv run ringsentinel-phase3 --transactions 5000
```

This writes controlled feature ablations, held-archetype generalization, permutation importance,
feature-distribution checks, exposure error, a hardened before/after benchmark, and replay milestones to
`results/phase3/`.

Generated datasets contain JSON Lines entity, event, and label tables plus ring and benign-community
ground truth, a manifest, and SHA-256 checksums. `--transactions` counts payment/capture events;
refund events are additional linked events.

The default ring-payment budget is 5% of payment volume while retaining all ten archetypes. Because
refund-abuse setup purchases and camouflage activity are not fraud-labeled, actual event prevalence is
measured from generated labels and may differ slightly. Override the budget with `--fraud-ratio`.

See [docs/data-model.md](docs/data-model.md) for the schema and ground-truth contract.
