# RingSentinel

Temporal network intelligence for coordinated payment abuse.

This repository contains the synthetic payment world and the **Phase 3 validated coordinated-abuse
pipeline**. It builds a temporal heterogeneous graph, extracts causal transaction/network features,
benchmarks simple and network-aware detectors, runs feature ablations and held-archetype tests, and
groups suspicious events into evidence-backed ring candidates. A deterministic evidence-query layer and
chronological replay simulator are ready for the future investigator/dashboard. It does not contain a
frontend, investigation agent, HTTP API, or GNN.

## Quick start

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
