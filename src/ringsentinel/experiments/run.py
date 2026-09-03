"""Run the Phase 2 cross-seed benchmark and write measured results."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import numpy as np

from ringsentinel.baselines.graph_heuristic import GraphHeuristicBaseline
from ringsentinel.baselines.rules import RuleBaseline
from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import DatasetBundle, GenerationConfig
from ringsentinel.detection.candidates import generate_ring_candidates
from ringsentinel.evaluation.metrics import (
    evaluate_events,
    evaluate_rings,
    labels_for_events,
    select_f1_threshold,
)
from ringsentinel.features.extractor import (
    NETWORK_FEATURES,
    TRANSACTION_FEATURES,
    FeatureTable,
    extract_event_features,
)
from ringsentinel.graph.builder import build_temporal_graph
from ringsentinel.models.tabular import BoostedTreeDetector


@dataclass(slots=True)
class PreparedDataset:
    seed: int
    bundle: DatasetBundle
    features: FeatureTable
    labels: np.ndarray
    generation_seconds: float
    graph_seconds: float
    feature_seconds: float
    graph_nodes: int
    graph_edges: int


def _prepare(seed: int, transactions: int) -> PreparedDataset:
    started = time.perf_counter()
    bundle = SyntheticPaymentGenerator(
        GenerationConfig(seed=seed, transactions=transactions)
    ).generate()
    generation_seconds = time.perf_counter() - started
    started = time.perf_counter()
    graph = build_temporal_graph(bundle)
    graph_seconds = time.perf_counter() - started
    started = time.perf_counter()
    features = extract_event_features(bundle)
    feature_seconds = time.perf_counter() - started
    return PreparedDataset(
        seed=seed,
        bundle=bundle,
        features=features,
        labels=labels_for_events(bundle, features.event_ids),
        generation_seconds=generation_seconds,
        graph_seconds=graph_seconds,
        feature_seconds=feature_seconds,
        graph_nodes=graph.graph.number_of_nodes(),
        graph_edges=graph.graph.number_of_edges(),
    )


def _mean_std(values: list[float]) -> dict[str, float]:
    return {"mean": mean(values), "std": pstdev(values) if len(values) > 1 else 0.0}


def _aggregate(folds: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate: dict[str, Any] = {}
    metric_names = (
        "precision",
        "recall",
        "f1",
        "pr_auc",
        "false_positive_rate",
        "ring_detection_rate",
        "exposure_weighted_recall",
        "benign_communities_flagged",
        "candidate_count",
        "threshold",
        "runtime_seconds",
    )
    for model_name in sorted({fold["model"] for fold in folds}):
        records = [fold for fold in folds if fold["model"] == model_name]
        aggregate[model_name] = {
            metric: _mean_std([float(record[metric]) for record in records])
            for metric in metric_names
        }
        delays = [
            float(record["mean_early_warning_delay_hours"])
            for record in records
            if record["mean_early_warning_delay_hours"] is not None
        ]
        aggregate[model_name]["mean_early_warning_delay_hours"] = (
            _mean_std(delays) if delays else {"mean": None, "std": None}
        )
    return aggregate


def _aggregate_scenarios(folds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for model_name in sorted({fold["model"] for fold in folds}):
        archetypes = sorted(
            {
                result["archetype"]
                for fold in folds
                if fold["model"] == model_name
                for result in fold["scenario_results"]
            }
        )
        for archetype in archetypes:
            records = [
                result
                for fold in folds
                if fold["model"] == model_name
                for result in fold["scenario_results"]
                if result["archetype"] == archetype
            ]
            delays = [
                float(record["early_warning_delay_hours"])
                for record in records
                if record["early_warning_delay_hours"] is not None
            ]
            output.append(
                {
                    "model": model_name,
                    "archetype": archetype,
                    "ring_detection_rate": mean(float(record["detected"]) for record in records),
                    "fraud_event_recall_mean": mean(
                        float(record["fraud_event_recall"]) for record in records
                    ),
                    "early_warning_delay_hours_mean": mean(delays) if delays else None,
                }
            )
    return output


def _aggregate_benign(folds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for model_name in sorted({fold["model"] for fold in folds}):
        archetypes = sorted(
            {
                result["archetype"]
                for fold in folds
                if fold["model"] == model_name
                for result in fold["benign_results"]
            }
        )
        for archetype in archetypes:
            records = [
                result
                for fold in folds
                if fold["model"] == model_name
                for result in fold["benign_results"]
                if result["archetype"] == archetype
            ]
            output.append(
                {
                    "model": model_name,
                    "archetype": archetype,
                    "flagged_seeds": sum(bool(record["flagged"]) for record in records),
                    "false_positive_rate": mean(float(record["flagged"]) for record in records),
                    "maximum_candidate_overlap": max(
                        int(record["maximum_candidate_overlap"]) for record in records
                    ),
                }
            )
    return output


def run_benchmark(seeds: tuple[int, ...], transactions: int) -> dict[str, Any]:
    if len(seeds) < 3:
        raise ValueError("at least three seeds are required for train/validation/test separation")
    benchmark_started = time.perf_counter()
    datasets = [_prepare(seed, transactions) for seed in seeds]
    folds: list[dict[str, Any]] = []
    all_features = TRANSACTION_FEATURES + NETWORK_FEATURES

    for test_index, test in enumerate(datasets):
        validation_index = (test_index + 1) % len(datasets)
        validation = datasets[validation_index]
        training = tuple(
            dataset
            for index, dataset in enumerate(datasets)
            if index not in {test_index, validation_index}
        )
        model_specs = (
            ("rules", RuleBaseline(), RuleBaseline.threshold),
            (
                "graph_heuristic",
                GraphHeuristicBaseline(),
                GraphHeuristicBaseline.threshold,
            ),
            (
                "transaction_hgb",
                BoostedTreeDetector(TRANSACTION_FEATURES, random_state=test.seed),
                None,
            ),
            (
                "network_aware_hgb",
                BoostedTreeDetector(all_features, random_state=test.seed),
                None,
            ),
        )
        for model_name, model, fixed_threshold in model_specs:
            started = time.perf_counter()
            if isinstance(model, BoostedTreeDetector):
                model.fit(
                    tuple(item.features for item in training),
                    tuple(item.labels for item in training),
                )
                validation_scores = model.predict_proba(validation.features)
                threshold = select_f1_threshold(validation.labels, validation_scores)
            else:
                threshold = float(fixed_threshold)
            test_scores = model.predict_proba(test.features)
            event_metrics = evaluate_events(test.labels, test_scores, threshold)
            score_by_event = dict(zip(test.features.event_ids, test_scores, strict=True))
            candidates = generate_ring_candidates(test.bundle, score_by_event, threshold=threshold)
            ring_metrics = evaluate_rings(test.bundle, candidates, score_by_event, threshold)
            runtime_seconds = time.perf_counter() - started
            folds.append(
                {
                    "test_seed": test.seed,
                    "validation_seed": validation.seed,
                    "training_seeds": [item.seed for item in training],
                    "model": model_name,
                    "threshold": threshold,
                    **event_metrics,
                    "candidate_count": len(candidates),
                    "true_rings_detected": ring_metrics.true_rings_detected,
                    "ring_detection_rate": ring_metrics.ring_detection_rate,
                    "exposure_weighted_recall": ring_metrics.exposure_weighted_recall,
                    "mean_early_warning_delay_hours": (ring_metrics.mean_early_warning_delay_hours),
                    "benign_communities_flagged": ring_metrics.benign_communities_flagged,
                    "scenario_results": list(ring_metrics.scenario_results),
                    "benign_results": list(ring_metrics.benign_results),
                    "runtime_seconds": runtime_seconds,
                    "top_candidates": [asdict(candidate) for candidate in candidates[:10]],
                }
            )

    return {
        "benchmark_version": "2.0.0",
        "seeds": list(seeds),
        "transactions_per_seed": transactions,
        "threshold_policy": {
            "rules": "fixed at 0.25 before evaluation",
            "graph_heuristic": "fixed at 0.50 before evaluation",
            "ml": "maximum F1 on a separate validation seed over thresholds 0.05..0.95",
        },
        "feature_sets": {
            "transaction": list(TRANSACTION_FEATURES),
            "network_temporal": list(NETWORK_FEATURES),
        },
        "dataset_runtime": [
            {
                "seed": item.seed,
                "generation_seconds": item.generation_seconds,
                "graph_seconds": item.graph_seconds,
                "feature_seconds": item.feature_seconds,
                "graph_nodes": item.graph_nodes,
                "graph_edges": item.graph_edges,
                "events": len(item.bundle.events),
            }
            for item in datasets
        ],
        "folds": folds,
        "aggregate": _aggregate(folds),
        "scenario_breakdown": _aggregate_scenarios(folds),
        "benign_hard_negatives": _aggregate_benign(folds),
        "total_runtime_seconds": time.perf_counter() - benchmark_started,
    }


def _write_markdown(result: dict[str, Any], path: Path) -> None:
    def measured(metrics: dict[str, Any], name: str) -> str:
        return f"{metrics[name]['mean']:.3f} +/- {metrics[name]['std']:.3f}"

    lines = [
        "# Phase 2 benchmark results",
        "",
        f"Seeds: `{result['seeds']}`; transactions per seed: `{result['transactions_per_seed']}`.",
        "",
        "Thresholds are fixed at 0.25 for rules and 0.50 for the graph heuristic; ML thresholds "
        "are selected by maximum F1 on a separate validation seed for each fold.",
        "",
        "## Aggregate event and ring metrics",
        "",
        "| Model | Precision | Recall | F1 | PR-AUC | FPR | Ring detection | Exposure recall |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model_name, metrics in result["aggregate"].items():
        lines.append(
            f"| {model_name} | {measured(metrics, 'precision')} | "
            f"{measured(metrics, 'recall')} | {measured(metrics, 'f1')} | "
            f"{measured(metrics, 'pr_auc')} | {measured(metrics, 'false_positive_rate')} | "
            f"{measured(metrics, 'ring_detection_rate')} | "
            f"{measured(metrics, 'exposure_weighted_recall')} |"
        )
    lines.extend(
        [
            "",
            "## Scenario breakdown",
            "",
            "| Model | Archetype | Ring detection | Fraud-event recall | Delay hours |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in result["scenario_breakdown"]:
        delay = row["early_warning_delay_hours_mean"]
        lines.append(
            f"| {row['model']} | {row['archetype']} | {row['ring_detection_rate']:.3f} | "
            f"{row['fraud_event_recall_mean']:.3f} | "
            f"{delay:.2f} |"
            if delay is not None
            else f"| {row['model']} | {row['archetype']} | {row['ring_detection_rate']:.3f} | "
            f"{row['fraud_event_recall_mean']:.3f} | - |"
        )
    lines.extend(
        [
            "",
            "## Benign hard negatives",
            "",
            "| Model | Community | Flagged seeds | False-positive rate | Max overlap |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in result["benign_hard_negatives"]:
        lines.append(
            f"| {row['model']} | {row['archetype']} | {row['flagged_seeds']} | "
            f"{row['false_positive_rate']:.3f} | {row['maximum_candidate_overlap']} |"
        )
    lines.extend(
        [
            "",
            "## Runtime",
            "",
            f"Total benchmark runtime: `{result['total_runtime_seconds']:.2f}` seconds.",
            "",
            "All values are measured outputs. Full fold, scenario, hard-negative, candidate, "
            "threshold, evidence, exposure, and runtime records are in `phase2_benchmark.json`.",
            "",
            "## Limitations",
            "",
            "Results are measured on synthetic ecosystems generated by one implementation. "
            "The very strong network-aware score should be challenged with more scenario variation "
            "and ablation tests before making external performance claims. Expected-loss rates "
            "remain assumptions, and model probabilities are not calibrated.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[101, 102, 103, 104, 105])
    parser.add_argument("--transactions", type=int, default=5_000)
    parser.add_argument("--output", type=Path, default=Path("results/phase2"))
    args = parser.parse_args(argv)
    result = run_benchmark(tuple(args.seeds), args.transactions)
    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "phase2_benchmark.json"
    json_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_markdown(result, args.output / "phase2_summary.md")
    print(
        json.dumps(
            {"output": str(args.output.resolve()), "aggregate": result["aggregate"]}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
