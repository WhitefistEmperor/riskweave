# Experiments

Run the five-seed Phase 2 benchmark with:

```powershell
uv run python -m ringsentinel.experiments.run --transactions 5000
```

Each fold trains on three seeds, selects ML thresholds on a fourth seed, and reports metrics on the held-out
fifth seed. Ground truth is used only for model fitting, validation-threshold selection, and evaluation;
feature extraction is causal and label-independent.
