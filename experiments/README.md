# Experiments

Run the five-seed Phase 2 benchmark with:

```powershell
uv run python -m ringsentinel.experiments.run --transactions 5000
```

Each fold trains on three seeds, selects ML thresholds on a fourth seed, and reports metrics on the held-out
fifth seed. Ground truth is used only for model fitting, validation-threshold selection, and evaluation;
feature extraction is causal and label-independent.

Run the Phase 3 validation suite with:

```powershell
uv run ringsentinel-phase3 --transactions 5000
```

The leave-one-archetype-out experiment removes every event touching the held ring's entities before
re-extracting train/validation features. Ground truth is used only to define those offline partitions and
to evaluate events, rings, and exposure; it is never available to feature extraction, candidate
generation, the evidence service, or replay.
