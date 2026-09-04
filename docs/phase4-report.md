# RingSentinel Phase 4 completion report

Phase 4 is complete as a local hackathon analyst application. The pre-existing
Milestone 1 commit was preserved and extended, not reimplemented. No GNN was added.
Generator, causal detector features, training procedure, and measured Phase 3 results
were not changed.

## Architecture and screens

- FastAPI calls the existing Python RingSentinel package directly.
- React/TypeScript uses the Sites/Vinext scaffold, shadcn primitives, Recharts, and Cytoscape.
- Overview: real payment stream, replay clock, observed-prefix metrics, candidate watch,
  uncalibrated event-score chart, and measured transaction/network comparison.
- Ring Explorer: typed graph nodes, zoom/pan, select/inspect, shared-resource highlighting,
  focus/fit, exact evidence queries, exposure definition, and chronological timeline.
- Investigator: cited computed observations with inspectable query outputs.
- Benchmark: three models, five feature-family comparisons, standard deviations,
  exposure errors, and limitations.
- Hard negatives: six legitimate communities with actual model outcomes and shared-resource graphs.
- Local development and production-preview servers both proxy to FastAPI. No database,
  auth service, queue, cloud account, deployment, or paid provider is required.

## Simulator and evidence

Seed 105 contains 14,051 entities and 5,104 events. The compact window replays 104
events and retains earlier history in prefix computations. Controls: start/pause,
step, reset, and 1×/2×/4× playback. Original event timestamps are preserved.

Focus activation: 2026-01-03 14:06:16 UTC (explicit demo truth).
First matched candidate: 14:14:16 UTC, eight minutes later.
At first detection the candidate has two customers and two events.
An earlier isolated threshold alert at 2026-01-02 17:32:56 UTC is visibly disclosed;
it did not form a candidate. Eight minutes is not average performance.

Live candidate navigation keeps the current prefix. Sidebar Explorer explicitly
opens the completed ecosystem. Candidate IDs change with membership; they are
snapshot identifiers, not persistent case IDs. The timeline separates the first
suspicious event from the first connected precursor and does not assign a final
risk score to an earlier timestamp.

All eleven grouped evidence panels expose computed queries: sharing devices/IPs/
cards/addresses/payouts, merchant relationships, temporal activity, refund patterns,
exposure, member behavior, and candidate details. Absence of evidence is explicit.

## Investigator

Default: deterministic evidence fallback, labeled in the UI. Questions select
allowlisted queries. Factual sentences are rendered from those query results and
carry query/path citations. The optional OpenAI provider selects and orders fact IDs
under a strict schema; it cannot supply free-form claims or classify fraud.
Malformed/unavailable provider responses fall back visibly. No live paid-provider
test is claimed; the HTTP/schema contract is tested with a stub transport.

This is bounded extractive question answering, not an unconstrained conversational
agent. It will not infer a person's identity, intent, causal model attribution, or
unsupported comparisons. Candidate-versus-hostel questions explicitly point to the
separate measured hard-negative view instead of inventing distinctions.

## Preserved benchmark

Five held-out synthetic ecosystems; means from the unchanged Phase 3 artifact:

| Model | PR-AUC | Recall | F1 | Event FPR | Ring detection |
|---|---:|---:|---:|---:|---:|
| Transaction-only | 0.199 | 0.154 | 0.243 | 0.55% | 30% |
| Graph heuristic | 0.321 | 0.287 | 0.307 | 2.75% | 28% |
| Network-aware | 0.971 | 0.939 | 0.951 | 0.17% | 100% |

Exposure mean relative error: 8.14%; aggregate underestimation: 4.44%.
Estimated/actual aggregate: 461,382,462 / 482,834,643 minor units.
Detection recall is separate from exposure-estimation accuracy.

The graph heuristic flags five of six benign communities for seed 105; the
network-aware model flags none. Hostel: 24 customers, 35 events, maximum graph
score 0.800 at threshold 0.50 versus network score 0.697 at threshold 0.71.
That close margin is not a guarantee of perfect benign separation.

Phase 3 JSON SHA-256:
`42c0234331f2b467ccc296f6579478d2feaf7c71e9c159387b6674a09b27e976`.
A Git comparison with the Phase 3 checkpoint shows no changes to its results.

## Actual verification

| Check | Result |
|---|---|
| Full Python suite | 41 passed, 2 dependency deprecation warnings; final run 34.05 s |
| Python Ruff | Passed |
| Frontend application lint | Passed |
| TypeScript check | Passed |
| Production frontend build | Passed |
| Production-browser suite | 5 passed, about 1.1 min |
| Python wheel and source distribution | Passed |
| Archive hygiene | No node_modules, venv, generated datasets, outputs, or Python caches |
| Dependency installation | npm ls reports all declared packages present |

Browser coverage: mobile navigation; optional WebMCP emulated registry and invalid
action rejection; benchmark and benign-community results; grounded investigator
and unsupported questions; start/pause/step/reset; actual alert, prefix graph,
node inspection/focus/fit, evidence and timeline.

The optional WebMCP controls share visible application state and degrade gracefully.
Their contract was checked with an emulated registry, not native browser support.

## Repairs made transparently

- Native float conversion fixed NumPy boolean API serialization.
- A dataset lock and seed-based lookup fixed concurrent cold-start behavior.
- Prefix snapshots prevent later evidence from appearing during replay.
- Timeline labels distinguish first suspicious activity from connected precursor formation.
- Ablation hard-negative rates are correctly labeled community rates, not event FPR.
- Earlier isolated alert is disclosed outside the compact replay window.
- Mobile drawer now closes when navigating.
- Local production API proxy was added and tested.
- Python sdist explicitly scopes backend assets; the wheel bundles measured results.

None of these repairs changed the benchmark or detector.

## Startup

From repository root, terminal 1:

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

Open http://127.0.0.1:5173. Allow roughly 20–40 seconds for cold model preparation.
For stable presentation, replace the dev server with `npm run build` then
`npm start` in frontend. Stop running Python launchers before reinstalling on Windows.
No key is needed. Optional provider environment setup is in .env.example; .env is
not auto-loaded. Full demo script: docs/demo-flow.md.

## Tested checkpoints

- a58e1b9 — Backend/API (already committed before the usage interruption).
- effb338 — Dashboard + causal replay controls.
- 82cf0bf — Snapshot-safe Ring Explorer + evidence timeline.
- fb817b0 — Grounded investigator + safe provider fallback.
- c34bd55 — Measured benchmark + benign community views.
- Final polish/documentation checkpoint follows the verified source represented here.

## Files and screenshots

Primary work: src/ringsentinel/api/, investigation/investigator.py,
frontend/components/, frontend/hooks/use-console-tools.ts, frontend/lib/api.ts,
frontend/app/, tests/integration/test_demo_runtime.py, tests/unit/test_investigator.py,
frontend/tests/demo.spec.ts, package/lock configuration, README and docs.

Curated screenshots: docs/screenshots/phase4-overview.png, phase4-explorer.png,
phase4-timeline.png, phase4-investigator.png, phase4-benchmark.png,
phase4-hard-negatives.png. Current captures also live in ignored outputs/.
The unchanged scaffold UI catalog is committed as source, not dependency/cache data.

## Limitations and submission checklist

- Synthetic validation only; unknown real-world shift and merchant-collusion variability.
- Scores and synthetic loss-rate assumptions are not calibrated production probabilities.
- Investigator is bounded/extractive; optional paid provider has not been live-tested.
- No authentication or public-service hardening. Keep both services on localhost.
- npm audit reports 8 high, 2 moderate, 1 low findings in the locked scaffold/toolchain.
  Broad upgrades were not forced during the deadline; remediate before public deployment.
- Bundled UI catalog has upstream lint findings and is excluded from application lint;
  all TypeScript remains typechecked. The build reports a large client chunk.
- Replay is a deterministic prepared window with causal precomputed scores, not a
  production event-ingestion system. Only seed 105 is selectable in this demo.
- Full tables may scroll horizontally on mobile; desktop is the intended demo setting.

Before submission: rehearse the documented 3–5 minute flow, warm the app, record a
backup walkthrough, and package the repository/screenshots. Optional paid-provider
testing is only necessary if presenting that mode. No additional implementation phase
was started.
