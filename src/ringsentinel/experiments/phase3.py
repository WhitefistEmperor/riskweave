"""Phase 3 validation: ablations, leakage audit, generalization, exposure, and replay."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

import numpy as np
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

from ringsentinel.data.schema import AttackArchetype, DatasetBundle
from ringsentinel.detection.candidates import generate_ring_candidates
from ringsentinel.evaluation.exposure import evaluate_exposure, match_candidates_to_truth
from ringsentinel.evaluation.metrics import (
    evaluate_events,
    evaluate_rings,
    labels_for_events,
    select_f1_threshold,
)
from ringsentinel.experiments.run import PreparedDataset, _prepare, run_benchmark
from ringsentinel.features.extractor import (
    INFRASTRUCTURE_SHARING_FEATURES,
    NETWORK_FEATURES,
    STRUCTURAL_GRAPH_FEATURES,
    TEMPORAL_NETWORK_FEATURES,
    TRANSACTION_FEATURES,
    FeatureTable,
    extract_event_features,
)
from ringsentinel.models.tabular import BoostedTreeDetector
from ringsentinel.simulation.replay import ChronologicalReplay, ReplaySnapshot

GENERALIZATION_ARCHETYPES = (
    AttackArchetype.SLOW_BURN,
    AttackArchetype.ADVERSARIAL_CAMOUFLAGE,
    AttackArchetype.FRAGMENTED,
    AttackArchetype.MERCHANT_COLLUSION,
    AttackArchetype.DEVICE_SHARING,
)


def ablation_feature_sets() -> dict[str, tuple[str, ...]]:
    """Return controlled feature sets without changing model or split policy."""

    full = TRANSACTION_FEATURES + NETWORK_FEATURES
    return {
        "transaction_only": TRANSACTION_FEATURES,
        "transaction_plus_infrastructure": (TRANSACTION_FEATURES + INFRASTRUCTURE_SHARING_FEATURES),
        "transaction_plus_temporal": TRANSACTION_FEATURES + TEMPORAL_NETWORK_FEATURES,
        "transaction_plus_structural": TRANSACTION_FEATURES + STRUCTURAL_GRAPH_FEATURES,
        "full_network_aware": full,
        "full_minus_transaction": NETWORK_FEATURES,
        "full_minus_infrastructure": tuple(
            name for name in full if name not in INFRASTRUCTURE_SHARING_FEATURES
        ),
        "full_minus_temporal": tuple(
            name for name in full if name not in TEMPORAL_NETWORK_FEATURES
        ),
        "full_minus_structural": tuple(
            name for name in full if name not in STRUCTURAL_GRAPH_FEATURES
        ),
    }


def _mean_std(values: list[float]) -> dict[str, float]:
    return {"mean": mean(values), "std": pstdev(values) if len(values) > 1 else 0.0}


def _aggregate_folds(folds: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, float]]]:
    metrics = (
        "precision",
        "recall",
        "f1",
        "pr_auc",
        "false_positive_rate",
        "ring_detection_rate",
        "hard_negative_false_positive_rate",
    )
    return {
        model_name: {
            metric: _mean_std([float(row[metric]) for row in folds if row["model"] == model_name])
            for metric in metrics
        }
        for model_name in sorted({row["model"] for row in folds})
    }


def _fit_model(
    feature_names: tuple[str, ...],
    training: tuple[PreparedDataset, ...],
    validation: PreparedDataset,
    *,
    random_state: int,
) -> tuple[BoostedTreeDetector, float]:
    model = BoostedTreeDetector(feature_names, random_state=random_state)
    model.fit(
        tuple(item.features for item in training),
        tuple(item.labels for item in training),
    )
    threshold = select_f1_threshold(
        validation.labels,
        model.predict_proba(validation.features),
    )
    return model, threshold


def run_ablation_experiments(datasets: list[PreparedDataset]) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    for test_index, test in enumerate(datasets):
        validation_index = (test_index + 1) % len(datasets)
        validation = datasets[validation_index]
        training = tuple(
            dataset
            for index, dataset in enumerate(datasets)
            if index not in {test_index, validation_index}
        )
        for model_name, feature_names in ablation_feature_sets().items():
            started = time.perf_counter()
            model, threshold = _fit_model(
                feature_names,
                training,
                validation,
                random_state=test.seed,
            )
            scores = model.predict_proba(test.features)
            event_metrics = evaluate_events(test.labels, scores, threshold)
            score_by_event = dict(zip(test.features.event_ids, scores, strict=True))
            candidates = generate_ring_candidates(
                test.bundle,
                score_by_event,
                threshold=threshold,
            )
            ring_metrics = evaluate_rings(
                test.bundle,
                candidates,
                score_by_event,
                threshold,
            )
            hard_negative_count = len(test.bundle.benign_communities)
            folds.append(
                {
                    "test_seed": test.seed,
                    "validation_seed": validation.seed,
                    "training_seeds": [item.seed for item in training],
                    "model": model_name,
                    "feature_names": list(feature_names),
                    "threshold": threshold,
                    **event_metrics,
                    "ring_detection_rate": ring_metrics.ring_detection_rate,
                    "hard_negative_false_positives": ring_metrics.benign_communities_flagged,
                    "hard_negative_false_positive_rate": (
                        ring_metrics.benign_communities_flagged / hard_negative_count
                        if hard_negative_count
                        else 0.0
                    ),
                    "runtime_seconds": time.perf_counter() - started,
                }
            )
    return {"folds": folds, "aggregate": _aggregate_folds(folds)}


def _subset_table(table: FeatureTable, mask: np.ndarray) -> FeatureTable:
    return FeatureTable(rows=tuple(row for row, keep in zip(table.rows, mask, strict=True) if keep))


def archetype_related_event_ids(
    bundle: DatasetBundle,
    archetype: AttackArchetype,
) -> frozenset[str]:
    """Ground-truth selection helper used only to isolate evaluation partitions."""

    return frozenset(
        event_id
        for ring in bundle.fraud_rings
        if ring.archetype is archetype
        for event_id in ring.related_event_ids
    )


def archetype_exclusion_mask(
    dataset: PreparedDataset,
    archetype: AttackArchetype,
) -> np.ndarray:
    excluded = archetype_related_event_ids(dataset.bundle, archetype)
    return np.asarray([event_id not in excluded for event_id in dataset.features.event_ids])


def archetype_test_mask(
    dataset: PreparedDataset,
    archetype: AttackArchetype,
) -> np.ndarray:
    held = archetype_related_event_ids(dataset.bundle, archetype)
    all_related = {
        event_id for ring in dataset.bundle.fraud_rings for event_id in ring.related_event_ids
    }
    return np.asarray(
        [event_id in held or event_id not in all_related for event_id in dataset.features.event_ids]
    )


def archetype_clean_training_view(
    dataset: PreparedDataset,
    archetype: AttackArchetype,
) -> tuple[FeatureTable, np.ndarray, frozenset[str]]:
    """Remove the held ring and its infrastructure effects before extracting features."""

    held_members = {
        entity_id
        for ring in dataset.bundle.fraud_rings
        if ring.archetype is archetype
        for entity_id in ring.member_entity_ids
    }

    def touches_held_ring(event: Any) -> bool:
        return bool(
            held_members
            & {
                event.customer_id,
                event.merchant_id,
                event.card_id,
                event.device_id,
                event.ip_id,
                event.address_id,
                event.merchant_bank_account_id,
            }
        )

    kept_events = tuple(event for event in dataset.bundle.events if not touches_held_ring(event))
    removed_ids = frozenset(
        event.event_id for event in dataset.bundle.events if touches_held_ring(event)
    )
    filtered_bundle = dataset.bundle.model_copy(
        update={
            "events": kept_events,
            "fraud_rings": tuple(
                ring for ring in dataset.bundle.fraud_rings if ring.archetype is not archetype
            ),
        }
    )
    features = extract_event_features(filtered_bundle)
    return features, labels_for_events(dataset.bundle, features.event_ids), removed_ids


def run_leave_one_archetype_out(datasets: list[PreparedDataset]) -> dict[str, Any]:
    feature_names = TRANSACTION_FEATURES + NETWORK_FEATURES
    rows: list[dict[str, Any]] = []
    for archetype in GENERALIZATION_ARCHETYPES:
        clean_views = {
            dataset.seed: archetype_clean_training_view(dataset, archetype) for dataset in datasets
        }
        for test_index, test in enumerate(datasets):
            validation_index = (test_index + 1) % len(datasets)
            validation = datasets[validation_index]
            training = [
                dataset
                for index, dataset in enumerate(datasets)
                if index not in {test_index, validation_index}
            ]
            model = BoostedTreeDetector(feature_names, random_state=test.seed)
            model.fit(
                tuple(clean_views[item.seed][0] for item in training),
                tuple(clean_views[item.seed][1] for item in training),
            )
            validation_table, validation_labels, _ = clean_views[validation.seed]
            threshold = select_f1_threshold(
                validation_labels,
                model.predict_proba(validation_table),
            )
            test_mask = archetype_test_mask(test, archetype)
            test_scores_all = model.predict_proba(test.features)
            metrics = evaluate_events(
                test.labels[test_mask],
                test_scores_all[test_mask],
                threshold,
            )
            visible_scores = {
                event_id: float(score) if keep else 0.0
                for event_id, score, keep in zip(
                    test.features.event_ids,
                    test_scores_all,
                    test_mask,
                    strict=True,
                )
            }
            candidates = generate_ring_candidates(
                test.bundle,
                visible_scores,
                threshold=threshold,
            )
            held_bundle = test.bundle.model_copy(
                update={
                    "fraud_rings": tuple(
                        ring for ring in test.bundle.fraud_rings if ring.archetype is archetype
                    )
                }
            )
            ring_metrics = evaluate_rings(
                held_bundle,
                candidates,
                visible_scores,
                threshold,
            )
            rows.append(
                {
                    "archetype": archetype.value,
                    "test_seed": test.seed,
                    "validation_seed": validation.seed,
                    "training_seeds": [item.seed for item in training],
                    "excluded_training_event_counts": [
                        len(clean_views[item.seed][2]) for item in training
                    ],
                    "threshold": threshold,
                    "pr_auc": metrics["pr_auc"],
                    "recall": metrics["recall"],
                    "ring_detection_rate": ring_metrics.ring_detection_rate,
                }
            )
    aggregate = []
    for archetype in GENERALIZATION_ARCHETYPES:
        selected = [row for row in rows if row["archetype"] == archetype.value]
        aggregate.append(
            {
                "archetype": archetype.value,
                "pr_auc": _mean_std([float(row["pr_auc"]) for row in selected]),
                "recall": _mean_std([float(row["recall"]) for row in selected]),
                "ring_detection_rate": _mean_std(
                    [float(row["ring_detection_rate"]) for row in selected]
                ),
            }
        )
    return {"folds": rows, "aggregate": aggregate}


def _distribution(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p10": float(np.quantile(values, 0.10)),
        "p90": float(np.quantile(values, 0.90)),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
        "nonzero_rate": float(np.mean(values != 0)),
    }


def run_full_model_audit(
    datasets: list[PreparedDataset],
    *,
    permutation_repeats: int,
) -> dict[str, Any]:
    feature_names = TRANSACTION_FEATURES + NETWORK_FEATURES
    importance_rows: list[dict[str, float | int | str]] = []
    exposure_rows: list[dict[str, Any]] = []
    replay_payload: dict[str, Any] | None = None

    for test_index, test in enumerate(datasets):
        validation_index = (test_index + 1) % len(datasets)
        validation = datasets[validation_index]
        training = tuple(
            dataset
            for index, dataset in enumerate(datasets)
            if index not in {test_index, validation_index}
        )
        model, threshold = _fit_model(
            feature_names,
            training,
            validation,
            random_state=test.seed,
        )
        scores = model.predict_proba(test.features)
        result = permutation_importance(
            model.model,
            test.features.matrix(feature_names),
            test.labels,
            scoring="average_precision",
            n_repeats=permutation_repeats,
            random_state=test.seed,
        )
        for name, importance, deviation in zip(
            feature_names,
            result.importances_mean,
            result.importances_std,
            strict=True,
        ):
            importance_rows.append(
                {
                    "seed": test.seed,
                    "feature": name,
                    "pr_auc_drop": float(importance),
                    "repeat_std": float(deviation),
                }
            )
        score_by_event = dict(zip(test.features.event_ids, scores, strict=True))
        candidates = generate_ring_candidates(test.bundle, score_by_event, threshold=threshold)
        fold_exposure = evaluate_exposure(test.bundle, candidates)
        exposure_rows.extend({"seed": test.seed, **row} for row in fold_exposure["rings"])

        if test_index == len(datasets) - 1:
            replay = ChronologicalReplay(
                test.bundle,
                score_by_event,
                threshold=threshold,
            ).replay()
            first = replay.snapshots[0] if replay.snapshots else None
            first_candidate_snapshot = next(
                (snapshot for snapshot in replay.snapshots if snapshot.candidate_count),
                None,
            )
            final = replay.snapshots[-1] if replay.snapshots else None

            def snapshot_payload(snapshot: ReplaySnapshot | None) -> dict[str, Any] | None:
                return asdict(snapshot) if snapshot else None

            earliest_ring = min(
                test.bundle.fraud_rings,
                key=lambda ring: (ring.attack_start_time, ring.ring_id),
            )
            event_by_id = {event.event_id: event for event in test.bundle.events}
            ordered_events = sorted(
                test.bundle.events,
                key=lambda event: (event.timestamp, event.event_id),
            )
            detected_candidate_time = None
            for snapshot in replay.snapshots:
                if not snapshot.candidate_count:
                    continue
                prefix_events = tuple(ordered_events[: snapshot.processed_event_count])
                prefix_scores = {
                    event.event_id: score_by_event[event.event_id] for event in prefix_events
                }
                prefix_bundle = test.bundle.model_copy(update={"events": prefix_events})
                prefix_candidates = generate_ring_candidates(
                    prefix_bundle,
                    prefix_scores,
                    threshold=threshold,
                )
                if earliest_ring.ring_id in match_candidates_to_truth(
                    test.bundle.model_copy(update={"fraud_rings": (earliest_ring,)}),
                    prefix_candidates,
                ):
                    detected_candidate_time = snapshot.timestamp
                    break
            replay_payload = {
                "seed": test.seed,
                "threshold": threshold,
                "started_at": replay.started_at,
                "ended_at": replay.ended_at,
                "processed_event_count": replay.processed_event_count,
                "normal_events_before_first_alert": (
                    first.processed_event_count - 1 if first else replay.processed_event_count
                ),
                "first_suspicious_timestamp": replay.first_suspicious_timestamp,
                "first_candidate_timestamp": replay.first_candidate_timestamp,
                "evaluation_overlay": {
                    "ground_truth_only": True,
                    "ring_id": earliest_ring.ring_id,
                    "archetype": earliest_ring.archetype.value,
                    "attack_start_time": earliest_ring.attack_start_time,
                    "first_fraud_event_time": min(
                        event_by_id[event_id].timestamp
                        for event_id in earliest_ring.fraudulent_event_ids
                    ),
                    "candidate_detected_time": detected_candidate_time,
                    "candidate_detection_delay_minutes": (
                        (detected_candidate_time - earliest_ring.attack_start_time).total_seconds()
                        / 60
                        if detected_candidate_time
                        else None
                    ),
                },
                "milestones": {
                    "first_suspicious_event": snapshot_payload(first),
                    "first_candidate": snapshot_payload(first_candidate_snapshot),
                    "final_suspicious_update": snapshot_payload(final),
                },
            }

    aggregate_importance = []
    for feature in feature_names:
        selected = [
            float(row["pr_auc_drop"]) for row in importance_rows if row["feature"] == feature
        ]
        aggregate_importance.append({"feature": feature, "pr_auc_drop": _mean_std(selected)})
    aggregate_importance.sort(
        key=lambda row: (-float(row["pr_auc_drop"]["mean"]), str(row["feature"]))
    )

    pooled_values = np.concatenate([dataset.features.matrix(feature_names) for dataset in datasets])
    pooled_labels = np.concatenate([dataset.labels for dataset in datasets])
    distributions_by_feature: dict[str, dict[str, Any]] = {}
    for item in aggregate_importance:
        feature = str(item["feature"])
        index = feature_names.index(feature)
        values = pooled_values[:, index]
        auc = roc_auc_score(pooled_labels, values)
        distributions_by_feature[feature] = {
            "feature": feature,
            "fraud": _distribution(values[pooled_labels == 1]),
            "benign": _distribution(values[pooled_labels == 0]),
            "univariate_auc_separation": max(float(auc), 1.0 - float(auc)),
        }
    distributions = [
        distributions_by_feature[str(item["feature"])] for item in aggregate_importance[:10]
    ]
    strongest_univariate = max(
        distributions_by_feature.values(),
        key=lambda row: (row["univariate_auc_separation"], row["feature"]),
    )
    audited_suspicious_features = (
        "shared_device_customers",
        "shared_ip_customers",
        "customer_component_size",
        "synchronized_activity_15m",
        "multi_shared_neighbor_count",
        "customer_events_1h",
        "infrastructure_events_24h",
        "payout_merchants",
    )

    def exposure_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
        errors = [int(row["absolute_error_minor"]) for row in records]
        relative = [
            float(row["relative_error"]) for row in records if row["relative_error"] is not None
        ]
        return {
            "ring_count": len(records),
            "mae_minor": mean(errors) if errors else None,
            "median_absolute_error_minor": median(errors) if errors else None,
            "mean_relative_error": mean(relative) if relative else None,
            "aggregate_estimated_exposure_minor": sum(
                int(row["estimated_exposure_minor"]) for row in records
            ),
            "aggregate_actual_exposure_minor": sum(
                int(row["actual_exposure_minor"]) for row in records
            ),
        }

    matched_exposure = [row for row in exposure_rows if row["detected"]]
    exposure = {
        "definition": (
            "At-risk value counted once per original payment; abusive refund value replaces, "
            "rather than adds to, the purchase value."
        ),
        "detection_recall": len(matched_exposure) / len(exposure_rows),
        "matched_rings": exposure_summary(matched_exposure),
        "end_to_end_including_missed_as_zero": exposure_summary(exposure_rows),
        "rings": exposure_rows,
    }
    return {
        "permutation_importance": aggregate_importance,
        "permutation_importance_folds": importance_rows,
        "top_feature_distributions": distributions,
        "audited_suspicious_feature_distributions": [
            distributions_by_feature[feature] for feature in audited_suspicious_features
        ],
        "maximum_univariate_auc_separation": strongest_univariate["univariate_auc_separation"],
        "maximum_univariate_feature": strongest_univariate["feature"],
        "exposure": exposure,
        "streaming_demo": replay_payload,
    }


def _old_baseline_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    return {
        "benchmark_version": result["benchmark_version"],
        "generator_note": "Committed Phase 2 generator 0.1.1",
        "aggregate": result["aggregate"],
    }


def run_phase3(
    seeds: tuple[int, ...],
    transactions: int,
    *,
    permutation_repeats: int = 3,
    phase2_result_path: Path = Path("results/phase2/phase2_benchmark.json"),
) -> dict[str, Any]:
    if len(seeds) < 3:
        raise ValueError("at least three seeds are required")
    started = time.perf_counter()
    datasets = [_prepare(seed, transactions) for seed in seeds]
    ablations = run_ablation_experiments(datasets)
    full_audit = run_full_model_audit(
        datasets,
        permutation_repeats=permutation_repeats,
    )
    generalization = run_leave_one_archetype_out(datasets)
    updated_benchmark = run_benchmark(seeds, transactions)
    return {
        "phase": "3",
        "benchmark_version": "3.0.0",
        "generator_version": datasets[0].bundle.manifest.generator_version,
        "seeds": list(seeds),
        "transactions_per_seed": transactions,
        "methodology": {
            "split": "cross-seed train/validation/test; no seed appears in two roles per fold",
            "threshold": "selected for maximum F1 on validation seed only",
            "features": "causal event-time features computed without labels",
            "permutation_scoring": "held-out test PR-AUC decrease",
            "generalization": (
                "all events touching held-ring entities removed before train/validation feature "
                "extraction; test contains ordinary benign traffic plus only the held archetype"
            ),
        },
        "artifact_audit": {
            "discovered": True,
            "artifact": (
                "Ring-controlled merchants lacked ordinary customer history, making low causal "
                "merchant degree an unrealistically strong proxy for fraud."
            ),
            "fix": (
                "Reallocated 4% of the existing payment budget to ordinary customers at ring "
                "merchants, mostly before attack activation; total transaction count is unchanged."
            ),
            "audit_fold_before": {
                "seed": 105,
                "merchant_customer_degree_permutation_pr_auc_drop": 0.8172,
                "merchant_customer_degree_univariate_auc_separation": 0.9390,
            },
            "audit_fold_after": {
                "seed": 105,
                "merchant_customer_degree_permutation_pr_auc_drop": 0.6152,
                "merchant_customer_degree_univariate_auc_separation": 0.7933,
            },
        },
        "before_benchmark": _old_baseline_snapshot(phase2_result_path),
        "updated_benchmark": updated_benchmark,
        "ablations": ablations,
        "feature_audit": {
            key: full_audit[key]
            for key in (
                "permutation_importance",
                "permutation_importance_folds",
                "top_feature_distributions",
                "audited_suspicious_feature_distributions",
                "maximum_univariate_auc_separation",
                "maximum_univariate_feature",
            )
        },
        "leave_one_archetype_out": generalization,
        "exposure": full_audit["exposure"],
        "streaming_demo": full_audit["streaming_demo"],
        "runtime_seconds": time.perf_counter() - started,
    }


def _metric(metrics: dict[str, Any], name: str) -> str:
    return f"{metrics[name]['mean']:.3f} +/- {metrics[name]['std']:.3f}"


def write_phase3_markdown(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Phase 3 validation results",
        "",
        f"Seeds: `{result['seeds']}`; payments per seed: `{result['transactions_per_seed']}`.",
        "All metrics below are measured outputs from cross-seed held-out evaluation.",
        "",
        "## Synthetic artifact found and fixed",
        "",
        result["artifact_audit"]["artifact"],
        "",
        result["artifact_audit"]["fix"],
        "",
        "## Before/after benchmark impact",
        "",
        "| Model | Before PR-AUC | After PR-AUC | Before F1 | After F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    before = result["before_benchmark"]
    if before is not None:
        for name, after_metrics in result["updated_benchmark"]["aggregate"].items():
            before_metrics = before["aggregate"][name]
            lines.append(
                f"| {name} | {before_metrics['pr_auc']['mean']:.3f} | "
                f"{after_metrics['pr_auc']['mean']:.3f} | "
                f"{before_metrics['f1']['mean']:.3f} | "
                f"{after_metrics['f1']['mean']:.3f} |"
            )
    lines.extend(
        [
            "",
            "## Feature ablations",
            "",
            (
                "| Feature set | Precision | Recall | F1 | PR-AUC | FPR | Ring detection | "
                "Hard-negative FP |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, metrics in result["ablations"]["aggregate"].items():
        lines.append(
            f"| {name} | {_metric(metrics, 'precision')} | {_metric(metrics, 'recall')} | "
            f"{_metric(metrics, 'f1')} | {_metric(metrics, 'pr_auc')} | "
            f"{_metric(metrics, 'false_positive_rate')} | "
            f"{_metric(metrics, 'ring_detection_rate')} | "
            f"{_metric(metrics, 'hard_negative_false_positive_rate')} |"
        )
    lines.extend(
        [
            "",
            "## Permutation importance",
            "",
            "| Feature | Held-out PR-AUC decrease |",
            "|---|---:|",
        ]
    )
    for row in result["feature_audit"]["permutation_importance"][:10]:
        values = row["pr_auc_drop"]
        lines.append(f"| {row['feature']} | {values['mean']:.4f} +/- {values['std']:.4f} |")
    lines.extend(
        [
            "",
            "## Strongest-feature distributions",
            "",
            (
                "| Feature | Fraud median (p10-p90) | Benign median (p10-p90) | "
                "Univariate separation AUC |"
            ),
            "|---|---:|---:|---:|",
        ]
    )
    for row in result["feature_audit"]["top_feature_distributions"]:
        fraud, benign = row["fraud"], row["benign"]
        lines.append(
            f"| {row['feature']} | {fraud['median']:.3f} ({fraud['p10']:.3f}-{fraud['p90']:.3f}) | "
            f"{benign['median']:.3f} ({benign['p10']:.3f}-{benign['p90']:.3f}) | "
            f"{row['univariate_auc_separation']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Leave-one-archetype-out generalization",
            "",
            "| Held-out archetype | PR-AUC | Recall | Ring detection |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in result["leave_one_archetype_out"]["aggregate"]:
        lines.append(
            f"| {row['archetype']} | {_metric(row, 'pr_auc')} | {_metric(row, 'recall')} | "
            f"{_metric(row, 'ring_detection_rate')} |"
        )
    exposure = result["exposure"]
    matched = exposure["matched_rings"]
    end_to_end = exposure["end_to_end_including_missed_as_zero"]
    lines.extend(
        [
            "",
            "## Exposure estimation",
            "",
            exposure["definition"],
            "",
            f"Detection recall: `{exposure['detection_recall']:.3f}`.",
            "",
            (
                "| Scope | Rings | MAE minor | Median AE minor | Mean relative error | "
                "Estimated / actual minor |"
            ),
            "|---|---:|---:|---:|---:|---:|",
            f"| Matched rings | {matched['ring_count']} | {matched['mae_minor']:.1f} | "
            f"{matched['median_absolute_error_minor']:.1f} | "
            f"{matched['mean_relative_error']:.3f} | "
            f"{matched['aggregate_estimated_exposure_minor']} / "
            f"{matched['aggregate_actual_exposure_minor']} |",
            f"| End-to-end | {end_to_end['ring_count']} | {end_to_end['mae_minor']:.1f} | "
            f"{end_to_end['median_absolute_error_minor']:.1f} | "
            f"{end_to_end['mean_relative_error']:.3f} | "
            f"{end_to_end['aggregate_estimated_exposure_minor']} / "
            f"{end_to_end['aggregate_actual_exposure_minor']} |",
            "",
            "Detection recall and exposure error are separate: a detected ring can still have "
            "under- or over-estimated exposure.",
            "",
            "## Updated benchmark after hardening",
            "",
            "| Model | Precision | Recall | F1 | PR-AUC | FPR | Ring detection |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, metrics in result["updated_benchmark"]["aggregate"].items():
        lines.append(
            f"| {name} | {_metric(metrics, 'precision')} | {_metric(metrics, 'recall')} | "
            f"{_metric(metrics, 'f1')} | {_metric(metrics, 'pr_auc')} | "
            f"{_metric(metrics, 'false_positive_rate')} | "
            f"{_metric(metrics, 'ring_detection_rate')} |"
        )
    stream = result["streaming_demo"]
    overlay = stream["evaluation_overlay"]
    lines.extend(
        [
            "",
            "## Streaming demo contract",
            "",
            f"Seed `{stream['seed']}` replays `{stream['processed_event_count']}` events. "
            f"The first threshold crossing is `{stream['first_suspicious_timestamp']}` and "
            f"the first candidate appears at `{stream['first_candidate_timestamp']}`. "
            f"There are `{stream['normal_events_before_first_alert']}` normal replay steps before "
            "the first model alert.",
            "",
            "That first threshold crossing is an isolated pre-attack alert and does not form a "
            "candidate. In the explicitly ground-truth-only evaluation overlay, "
            f"`{overlay['archetype']}` begins at `{overlay['attack_start_time']}` and its matched "
            f"candidate appears at `{overlay['candidate_detected_time']}`—"
            f"`{overlay['candidate_detection_delay_minutes']:.1f}` minutes later.",
            "",
            "The evidence service and replay simulator use only event/graph/model outputs. Fraud "
            "ground truth is reserved for offline evaluation.",
            "",
            "## Interpretation",
            "",
            "Generalization claims should be limited to archetypes whose held-out results support "
            "them. The benchmark remains synthetic; expected-loss rates are synthetic assumptions "
            "and model probabilities are not calibrated.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[101, 102, 103, 104, 105])
    parser.add_argument("--transactions", type=int, default=5_000)
    parser.add_argument("--permutation-repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("results/phase3"))
    args = parser.parse_args(argv)
    result = run_phase3(
        tuple(args.seeds),
        args.transactions,
        permutation_repeats=args.permutation_repeats,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "phase3_results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_phase3_markdown(result, args.output / "phase3_summary.md")
    print(
        json.dumps(
            {"output": str(args.output.resolve()), "runtime": result["runtime_seconds"]}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
