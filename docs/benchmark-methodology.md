# Benchmark methodology and presentation

The Phase 4 application loads `results/phase3/phase3_results.json` without changing
or recomputing its recorded evaluation metrics. Integration tests compare the API
model and ablation payloads exactly with the artifact. The full Phase 3 before/after
audit and weak results remain in `results/phase3/phase3_summary.md`.

Five held-out seeds (101–105) each contain 5,000 payments plus additional refunds.
For each fold, three ecosystems train the histogram-gradient-boosting model,
one selects its F1 threshold, and the held-out fifth is evaluated once. The local
demo reproduces seed 105: train 102/103/104, validate 101, test 105, threshold 0.71.
Seeds are disjoint; labels and scenario fields are excluded from detector features.
Feature extraction is chronological and tested for future-event leakage.

The UI reports event precision, recall, F1, PR-AUC and event FPR. Ring detection
is a separate ground-truth evaluation. Baseline hard-negative results are counts
of flagged benign communities (out of six). The ablation artifact's field named
`hard_negative_false_positive_rate` is **community flag count divided by six**,
not an event-level false-positive rate. The UI labels that distinction explicitly.
All standard deviations are population standard deviations across the five folds.

The ablation additions each start from transaction features. They are not cumulative.
The graph heuristic is a fixed sharing rule, not a learned GNN. Graph highlighting
shows observed sharing and must not be interpreted as per-case feature attribution.

Exposure error is evaluated against Phase 1 ring exposure: 50 matched rings,
mean relative error 8.1361%, aggregate estimate 461,382,462 minor units versus
482,834,643 actual (4.4429% underestimation). Purchases/refunds are counted once
per original payment. Detection recall and exposure-estimation error are distinct.

The Phase 3 audit found an unrealistically low merchant-history shortcut and added
normal traffic at ring merchants before final validation. Network PR-AUC moved
from 0.979 to 0.971; the post-hardening result is what the dashboard reports.
Merchant-collusion held-out PR-AUC was 0.803 ± 0.143, demonstrating seed variability.
Do not generalize these synthetic numbers to production fraud rates or calibrated
loss probabilities. Real data requires new training, validation, and monitoring.

The eight-minute example is one first matched ring, not average performance.
The full ecosystem has an earlier isolated threshold alert at 2026-01-02 17:32:56
UTC that does not form a candidate. The compact demo window begins later and its
clock preserves original event timestamps. The network benchmark's mean early
warning delay is about 20.95 hours; it must not be replaced by the demo's eight minutes.
