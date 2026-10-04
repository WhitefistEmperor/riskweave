# Private frozen-model temporal evaluation

Run `python -m ringsentinel.evaluation.temporal` locally with an operator-trusted
model artifact and pinned SHA-256. This tool evaluates the existing detector;
it does not retrain, calibrate, publish a model or approve production use.
Pickle/joblib can execute code: a matching hash alone does not make an unknown
model trustworthy. Use a known build-owned model, never an uploaded model.

Three separate UTF-8 JSON inputs are required. Keep inputs and reports in an
ignored private `work/` directory. Do not commit real payments, labels, reports
or personal identifiers. Reports omit event/customer IDs and per-event scores,
but label definitions and aggregate small cells can still be sensitive.

1. Payments use the existing strict `payments-v1` contract. CSV exports can be
   prepared with the explicit workflow in `docs/csv-payment-mapping.md`; retain
   its private provenance sidecar alongside the evaluation report. Ground truth is not
   attached to the inference input. Currency is singular; no FX conversion is
   performed. Non-INR model validity still requires independent validation.
2. Labels use `resolved-labels-v1` with `labels` containing `event_id`, strict
   boolean `is_fraud`, and timezone-aware `resolved_at`. Unknown/duplicate IDs,
   labels dated before their event and coercible string labels are rejected.
   Only resolved labels count; missing and delayed labels are not negatives.
3. The plan uses `temporal-evaluation-v1`, an operator `data_origin` declaration
   (`observed` or `synthetic-control`), `authorization_confirmed: true`, a
   meaningful `label_definition`, and timezone-aware `validation_start`,
   `test_start`, `test_end`, `labels_as_of`. Authorization/origin declarations
   are not independently verified permissions or provenance certificates.

Example plan (replace dates and definition for an authorized evaluation):

```json
{
  "schema_version": "temporal-evaluation-v1",
  "data_origin": "synthetic-control",
  "authorization_confirmed": true,
  "label_definition": "Synthetic control ground truth; not observed fraud.",
  "validation_start": "2026-01-01T00:00:00Z",
  "test_start": "2026-01-16T00:00:00Z",
  "test_end": "2026-02-01T00:00:00Z",
  "labels_as_of": "2026-03-03T00:00:00Z",
  "threshold_policy": "frozen",
  "false_positive_cost": 1,
  "false_negative_cost": 1
}
```

```powershell
$env:OMP_NUM_THREADS = '1'
.venv/Scripts/python -m ringsentinel.evaluation.temporal `
  --payments work/evaluation/payments.json `
  --labels work/evaluation/labels.json `
  --plan work/evaluation/plan.json `
  --model work/models/network-hgb.joblib `
  --model-sha256 'REPLACE_WITH_TRUSTED_BUILD_SHA256' `
  --output work/evaluation/report.json
```

Replace the quoted SHA placeholder with the trusted release digest. Do not
obtain a trust pin from an unknown uploaded pickle. The output directory must already exist. Existing reports are never overwritten.
Input files are individually bounded to 100 MB. Console failures return exit 2
with a sanitized error code, excluding paths and input contents. Read the input
contracts locally to resolve a failure; never publish raw validation exceptions.

Scoring retains pre-validation history and uses causal event features on events
strictly before `test_end`. Labels are joined after predictions. Windows are
half-open: validation includes `[validation_start, test_start)`; test includes
`[test_start, test_end)`. The default threshold is the frozen artifact threshold.
Optional `validation-cost` chooses from a fixed 0.01 grid plus the frozen
threshold, minimizes FP/FN relative cost on validation labels only and chooses
the highest threshold on ties. Validation labels must be resolved by `test_start`
for this selection; retrospective labels cannot tune a historical decision.
Both classes are required for threshold selection. Costs are operator-relative
error costs, not measured monetary loss, recoverable exposure or guaranteed savings.
This evaluation never changes the production model or threshold. Model/mapping
availability at historical event times is not established by this retrospective
command; freeze the evaluation plan before inspecting held-out test outcomes.

Reports record model/payment/label/plan hashes, Python/library versions, feature
names and a Python-package source-tree fingerprint, window label coverage, confusion
counts, precision/recall/FPR, average precision, raw-score Brier error, reliability
bins, event-type subgroups and validation/test customer overlap. Undefined metrics
and empty bins are `null`. Average precision is undefined here for a one-class
window. Brier error combines calibration and other properties; a low Brier value
alone does not establish calibration. Customer overlap makes the result a measure
of returning-customer behavior, not an unseen-customer generalization claim.

All reports explicitly set `production_ready: false`. Missing labels can create
selection bias. No confidence intervals, protected-group fairness audit, real
ring-ground-truth matching, feature-drift admission, prospective label-maturation
study or independent external validation is supplied. Those remain release work,
as do calibration/retraining on authorized data, versioned data mappings and
operating thresholds selected under actual review capacity and error costs.

The local smoke used a synthetic control with 55 validation and 49 test events,
zero missing control labels and the unchanged pinned build model. These counts
prove the command path, not observed-data accuracy or approval.

Method references: [scikit-learn metrics](https://scikit-learn.org/stable/modules/model_evaluation.html)
and [time-series evaluation](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data).
