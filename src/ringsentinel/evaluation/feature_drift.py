"""Label-independent descriptive feature shift; no significance or admission claims."""

import numpy as np


def distribution(values):
    # Scaling avoids overflow in mean/std for large finite input values.
    scale = float(np.max(np.abs(values))) or 1.0
    scaled = values / scale
    return dict(
        count=len(values),
        minimum=float(np.min(values)),
        maximum=float(np.max(values)),
        mean=float(np.mean(scaled) * scale),
        standard_deviation=float(np.std(scaled) * scale),
    )


def compare(reference, current):
    reference, current = np.asarray(reference, dtype=float), np.asarray(current, dtype=float)
    if (
        reference.ndim != 1
        or current.ndim != 1
        or not len(reference)
        or not len(current)
        or not np.isfinite(reference).all()
        or not np.isfinite(current).all()
    ):
        raise ValueError("Nonempty finite feature windows required")
    reference, current = np.sort(reference), np.sort(current)
    points = np.unique(np.concatenate((reference, current)))
    delta = np.abs(
        np.searchsorted(reference, points, side="right") / len(reference)
        - np.searchsorted(current, points, side="right") / len(current)
    )
    # These are descriptive empirical distances, not an independence-based KS test.
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        baseline, observed = distribution(reference), distribution(current)
        distance = float(np.sum(delta[:-1] * np.diff(points)))
        standard_deviation = baseline["standard_deviation"]
        standardized = (
            (observed["mean"] - baseline["mean"]) / standard_deviation
            if standard_deviation
            else None
        )
    if standardized is not None and not np.isfinite(standardized):
        raise ValueError("Unrepresentable standardized change")
    return dict(
        validation=baseline,
        test=observed,
        empirical_cdf_max_distance=float(np.max(delta)),
        wasserstein_1=distance,
        mean_change_in_validation_std=standardized,
        validation_constant=bool(reference[0] == reference[-1]),
        test_outside_validation_range_fraction=float(
            np.mean((current < reference[0]) | (current > reference[-1]))
        ),
    )


def diagnostics(table, plan, feature_names):
    names = tuple(feature_names)
    if not names or len(set(names)) != len(names):
        raise ValueError("Unique model feature names required")
    # Use the scoring table's causal prefix, not re-extracted isolated windows.
    windows = [
        tuple(row for row in table.rows if start <= row.timestamp < end)
        for start, end in (
            (plan.validation_start, plan.test_start),
            (plan.test_start, plan.test_end),
        )
    ]
    if any(not rows for rows in windows):
        raise ValueError("Nonempty feature windows required")
    features = {
        name: compare(
            [row.values[name] for row in windows[0]], [row.values[name] for row in windows[1]]
        )
        for name in names
    }
    return dict(
        schema_version="feature-shift-diagnostics-v1",
        labels_used=False,
        reference="validation-window-all-events",
        comparison="test-window-all-events",
        validation_events=len(windows[0]),
        test_events=len(windows[1]),
        features=features,
        admission_decision=None,
        limitations=[
            "Descriptive marginal distances, not p-values or confidence intervals.",
            "Correlated graph/history features and repeated customers are not independent samples.",
            "No universal drift cutoff, calibration, retraining or production approval.",
            "Validation window is not a certified training-population reference.",
            "Univariate comparisons do not establish joint or outcome-distribution stability.",
        ],
    )
