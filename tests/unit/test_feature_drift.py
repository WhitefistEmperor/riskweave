"""Descriptive input shift must be accurate, causal and independent of outcome labels."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.stats import ks_2samp, wasserstein_distance

from ringsentinel.evaluation.feature_drift import compare, diagnostics
from ringsentinel.features.extractor import EventFeatureRow, FeatureTable


def test_shift_matches_hand_arithmetic_and_unchanged_samples():
    report = compare([0, 0, 2, 2], [2, 2, 4, 4])
    assert report["empirical_cdf_max_distance"] == 0.5
    assert report["wasserstein_1"] == report["mean_change_in_validation_std"] == 2
    assert report["test_outside_validation_range_fraction"] == 0.5
    assert report["validation"]["mean"] == report["validation"]["standard_deviation"] == 1
    unchanged = compare([0, 1, 1, 2], [2, 1, 0, 1])
    assert unchanged["empirical_cdf_max_distance"] == unchanged["wasserstein_1"] == 0
    assert unchanged["mean_change_in_validation_std"] == 0


def test_unequal_sample_sizes_ties_and_negatives_match_independent_library():
    reference = [-4, -2, -2, 0, 0, 1]
    current = [-2, 0, 0, 0, 3, 5, 8]
    report = compare(reference, current)
    assert report["empirical_cdf_max_distance"] == pytest.approx(
        ks_2samp(reference, current).statistic
    )
    assert report["wasserstein_1"] == pytest.approx(wasserstein_distance(reference, current))
    assert report["test_outside_validation_range_fraction"] == pytest.approx(3 / 7)


def test_constant_reference_does_not_fabricate_standardized_shift():
    report = compare([0, 0, 0], [1, 1])
    assert report["validation_constant"] is True
    assert report["mean_change_in_validation_std"] is None
    assert report["wasserstein_1"] == report["empirical_cdf_max_distance"] == 1
    assert report["test_outside_validation_range_fraction"] == 1


@pytest.mark.parametrize(
    "reference,current", [([], [1]), ([1], []), ([np.nan], [1]), ([1], [np.inf]), ([[1]], [1])]
)
def test_nonfinite_empty_or_nonvector_inputs_fail(reference, current):
    with pytest.raises(ValueError):
        compare(reference, current)


def test_diagnostics_use_all_causal_rows_and_half_open_boundaries_without_ids_or_labels():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    plan = SimpleNamespace(
        validation_start=start,
        test_start=start + timedelta(days=1),
        test_end=start + timedelta(days=2),
    )
    table = FeatureTable(
        tuple(
            EventFeatureRow(f"private-event-{index}", time, {"a": value})
            for index, (time, value) in enumerate(
                [
                    (start - timedelta(seconds=1), 999),
                    (start, 0),
                    (plan.test_start - timedelta(seconds=1), 2),
                    (plan.test_start, 2),
                    (plan.test_end - timedelta(seconds=1), 4),
                    (plan.test_end, 999),
                ]
            )
        )
    )
    report = diagnostics(table, plan, ("a",))
    assert report["features"]["a"] == compare([0, 2], [2, 4])
    assert report["labels_used"] is False and report["admission_decision"] is None
    assert report["validation_events"] == report["test_events"] == 2
    assert "private-event" not in str(report)
    with pytest.raises(ValueError):
        diagnostics(table, plan, ("a", "a"))
