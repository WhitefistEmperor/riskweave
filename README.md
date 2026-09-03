# RingSentinel

Temporal network intelligence for coordinated payment abuse.

This repository contains the synthetic payment world and the **Phase 2 coordinated-abuse detection
pipeline**. It builds a temporal heterogeneous graph, extracts causal transaction/network features,
compares fixed transaction rules, a static graph heuristic, transaction-only boosted trees, and a
network-aware boosted-tree detector, then groups suspicious events into evidence-backed ring candidates.
It does not yet contain a frontend, investigation agent, API, or GNN.

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

Generated datasets contain JSON Lines entity, event, and label tables plus ring and benign-community
ground truth, a manifest, and SHA-256 checksums. `--transactions` counts payment/capture events;
refund events are additional linked events.

The default ring-payment budget is 5% of payment volume while retaining all ten archetypes. Because
refund-abuse setup purchases and camouflage activity are not fraud-labeled, actual event prevalence is
measured from generated labels and may differ slightly. Override the budget with `--fraud-ratio`.

See [docs/data-model.md](docs/data-model.md) for the schema and ground-truth contract.
