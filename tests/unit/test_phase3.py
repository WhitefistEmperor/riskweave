from __future__ import annotations

import json

from ringsentinel.data.generator import SyntheticPaymentGenerator
from ringsentinel.data.schema import AttackArchetype, EntityType, GenerationConfig
from ringsentinel.detection.candidates import generate_ring_candidates
from ringsentinel.evaluation.exposure import evaluate_exposure
from ringsentinel.experiments.phase3 import (
    ablation_feature_sets,
    archetype_clean_training_view,
    archetype_exclusion_mask,
    archetype_related_event_ids,
    archetype_test_mask,
)
from ringsentinel.experiments.run import _prepare
from ringsentinel.features.extractor import (
    INFRASTRUCTURE_SHARING_FEATURES,
    NETWORK_FEATURES,
    STRUCTURAL_GRAPH_FEATURES,
    TEMPORAL_NETWORK_FEATURES,
    TRANSACTION_FEATURES,
    extract_event_features,
)
from ringsentinel.investigation.evidence import RingEvidenceService
from ringsentinel.simulation.replay import ChronologicalReplay


def _perfect_candidates(seed: int = 72, transactions: int = 500):
    bundle = SyntheticPaymentGenerator(
        GenerationConfig(seed=seed, transactions=transactions)
    ).generate()
    labels = {label.subject_id: float(label.is_fraud) for label in bundle.event_labels}
    candidates = generate_ring_candidates(bundle, labels, threshold=0.5)
    return bundle, labels, candidates


def test_ablation_feature_sets_are_controlled_and_complete() -> None:
    families = (
        set(INFRASTRUCTURE_SHARING_FEATURES),
        set(STRUCTURAL_GRAPH_FEATURES),
        set(TEMPORAL_NETWORK_FEATURES),
    )
    assert all(
        not left & right for index, left in enumerate(families) for right in families[index + 1 :]
    )
    assert set(NETWORK_FEATURES) == set().union(*families)

    specs = ablation_feature_sets()
    full = set(TRANSACTION_FEATURES + NETWORK_FEATURES)
    assert set(specs) == {
        "transaction_only",
        "transaction_plus_infrastructure",
        "transaction_plus_temporal",
        "transaction_plus_structural",
        "full_network_aware",
        "full_minus_transaction",
        "full_minus_infrastructure",
        "full_minus_temporal",
        "full_minus_structural",
    }
    assert set(specs["full_network_aware"]) == full
    assert set(specs["full_minus_infrastructure"]) == full - families[0]
    assert set(specs["full_minus_structural"]) == full - families[1]
    assert set(specs["full_minus_temporal"]) == full - families[2]


def test_leave_one_archetype_out_masks_isolate_related_events() -> None:
    dataset = _prepare(73, 300)
    archetype = AttackArchetype.SLOW_BURN
    held_ids = archetype_related_event_ids(dataset.bundle, archetype)
    exclusion = archetype_exclusion_mask(dataset, archetype)
    test_mask = archetype_test_mask(dataset, archetype)
    all_related = {
        event_id for ring in dataset.bundle.fraud_rings for event_id in ring.related_event_ids
    }

    assert held_ids
    assert {
        event_id
        for event_id, keep in zip(dataset.features.event_ids, exclusion, strict=True)
        if not keep
    } == held_ids
    included = {
        event_id
        for event_id, keep in zip(dataset.features.event_ids, test_mask, strict=True)
        if keep
    }
    assert held_ids <= included
    assert not (included & (all_related - held_ids))

    clean_features, _, removed_ids = archetype_clean_training_view(dataset, archetype)
    held_members = {
        entity_id
        for ring in dataset.bundle.fraud_rings
        if ring.archetype is archetype
        for entity_id in ring.member_entity_ids
    }
    event_by_id = {event.event_id: event for event in dataset.bundle.events}
    assert held_ids < removed_ids
    for event_id in clean_features.event_ids:
        event = event_by_id[event_id]
        assert not held_members & {
            event.customer_id,
            event.merchant_id,
            event.card_id,
            event.device_id,
            event.ip_id,
            event.address_id,
            event.merchant_bank_account_id,
        }


def test_evidence_queries_are_deterministic_grounded_and_json_serializable() -> None:
    bundle, scores, candidates = _perfect_candidates()
    service = RingEvidenceService(bundle, candidates, scores=scores)
    candidate_id = candidates[0].candidate_id

    result = {
        "ring": service.get_candidate_ring(candidate_id),
        "members": service.get_ring_members(candidate_id),
        "devices": service.get_shared_devices(candidate_id),
        "ips": service.get_shared_ips(candidate_id),
        "cards": service.get_shared_cards(candidate_id),
        "addresses": service.get_shared_addresses(candidate_id),
        "payouts": service.get_shared_payout_accounts(candidate_id),
        "timeline": service.get_transaction_timeline(candidate_id),
        "refunds": service.get_refund_patterns(candidate_id),
        "merchants": service.get_merchant_relationships(candidate_id),
        "temporal": service.get_temporal_activity(candidate_id),
        "exposure": service.calculate_exposure(candidate_id),
        "behavior": service.compare_member_behavior(candidate_id),
    }

    assert json.loads(json.dumps(result)) == result
    assert result == {
        "ring": service.get_candidate_ring(candidate_id),
        "members": service.get_ring_members(candidate_id),
        "devices": service.get_shared_devices(candidate_id),
        "ips": service.get_shared_ips(candidate_id),
        "cards": service.get_shared_cards(candidate_id),
        "addresses": service.get_shared_addresses(candidate_id),
        "payouts": service.get_shared_payout_accounts(candidate_id),
        "timeline": service.get_transaction_timeline(candidate_id),
        "refunds": service.get_refund_patterns(candidate_id),
        "merchants": service.get_merchant_relationships(candidate_id),
        "temporal": service.get_temporal_activity(candidate_id),
        "exposure": service.calculate_exposure(candidate_id),
        "behavior": service.compare_member_behavior(candidate_id),
    }
    assert not any("fraud" in key or "truth" in key for key in result["ring"])


def test_perfect_detection_has_exact_exposure_estimates() -> None:
    bundle, _, candidates = _perfect_candidates(seed=74)
    result = evaluate_exposure(bundle, candidates)

    assert result["detection_recall"] == 1.0
    assert result["matched_rings"]["mae_minor"] == 0.0
    assert result["matched_rings"]["median_absolute_error_minor"] == 0.0
    assert (
        result["matched_rings"]["aggregate_estimated_exposure_minor"]
        == result["matched_rings"]["aggregate_actual_exposure_minor"]
    )


def test_replay_is_ordered_and_never_uses_future_scores() -> None:
    bundle, scores, _ = _perfect_candidates(seed=75)
    replay = ChronologicalReplay(bundle, scores, threshold=0.5).replay()

    assert replay.processed_event_count == len(bundle.events)
    assert replay.snapshots
    assert [item.timestamp for item in replay.snapshots] == sorted(
        item.timestamp for item in replay.snapshots
    )
    assert replay.first_candidate_timestamp is not None
    first_candidate = next(item for item in replay.snapshots if item.candidate_count)
    assert first_candidate.suspicious_event_count >= 2

    last_event = max(bundle.events, key=lambda event: (event.timestamp, event.event_id))
    changed_scores = dict(scores)
    changed_scores[last_event.event_id] = 1.0 - changed_scores[last_event.event_id]
    changed = ChronologicalReplay(bundle, changed_scores, threshold=0.5).replay()
    original_prefix = [item for item in replay.snapshots if item.timestamp < last_event.timestamp]
    changed_prefix = [item for item in changed.snapshots if item.timestamp < last_event.timestamp]
    assert original_prefix == changed_prefix


def test_full_feature_extraction_prefix_is_unchanged_by_future_events() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=76, transactions=400)).generate()
    full = extract_event_features(bundle)
    cutoff = len(bundle.events) // 2
    prefix = bundle.model_copy(update={"events": bundle.events[:cutoff]})

    assert extract_event_features(prefix).rows == full.rows[:cutoff]


def test_ring_merchants_have_benign_preattack_customer_history() -> None:
    bundle = SyntheticPaymentGenerator(GenerationConfig(seed=77, transactions=1_000)).generate()
    entity_types = {entity.entity_id: entity.entity_type for entity in bundle.entities}
    event_labels = {label.subject_id: label.is_fraud for label in bundle.event_labels}

    for ring in bundle.fraud_rings:
        merchants = {
            entity_id
            for entity_id in ring.member_entity_ids
            if entity_types[entity_id] is EntityType.MERCHANT
        }
        background = [
            event
            for event in bundle.events
            if event.merchant_id in merchants
            and event.timestamp < ring.attack_start_time
            and not event_labels[event.event_id]
        ]
        assert background
