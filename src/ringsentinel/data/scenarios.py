"""Fraud-ring scenario catalog used by the synthetic generator."""

from __future__ import annotations

from dataclasses import dataclass

from ringsentinel.data.schema import AttackArchetype


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    archetype: AttackArchetype
    code: str
    description: str
    synthetic_expected_loss_rate: float
    temporal_pattern: str


SCENARIO_CATALOG: dict[AttackArchetype, ScenarioSpec] = {
    AttackArchetype.OBVIOUS_COORDINATED: ScenarioSpec(
        AttackArchetype.OBVIOUS_COORDINATED,
        "A",
        "High-connectivity ring with synchronized payment activity.",
        0.90,
        "burst",
    ),
    AttackArchetype.FRAGMENTED: ScenarioSpec(
        AttackArchetype.FRAGMENTED,
        "B",
        "Sparse subgroups connected indirectly through merchant payout infrastructure.",
        0.75,
        "fragmented",
    ),
    AttackArchetype.SLOW_BURN: ScenarioSpec(
        AttackArchetype.SLOW_BURN,
        "C",
        "Low-velocity coordinated activity spread across days.",
        0.65,
        "slow",
    ),
    AttackArchetype.DEVICE_SHARING: ScenarioSpec(
        AttackArchetype.DEVICE_SHARING,
        "D",
        "Distinct identities and cards reuse a small device pool.",
        0.85,
        "burst",
    ),
    AttackArchetype.MERCHANT_COLLUSION: ScenarioSpec(
        AttackArchetype.MERCHANT_COLLUSION,
        "E",
        "Several merchants settle to a common controlled payout account.",
        0.88,
        "merchant",
    ),
    AttackArchetype.REFUND_ABUSE: ScenarioSpec(
        AttackArchetype.REFUND_ABUSE,
        "F",
        "Normal-looking purchases are followed by synchronized refund waves.",
        0.80,
        "refund",
    ),
    AttackArchetype.SYNTHETIC_IDENTITIES: ScenarioSpec(
        AttackArchetype.SYNTHETIC_IDENTITIES,
        "G",
        "Separate synthetic identities overlap on hidden address and device infrastructure.",
        0.78,
        "identity",
    ),
    AttackArchetype.RING_EXPANSION: ScenarioSpec(
        AttackArchetype.RING_EXPANSION,
        "H",
        "A small initial group progressively activates recruited accounts.",
        0.82,
        "expansion",
    ),
    AttackArchetype.COOPERATING_RINGS: ScenarioSpec(
        AttackArchetype.COOPERATING_RINGS,
        "I",
        "Two initially separate groups later share infrastructure.",
        0.86,
        "merger",
    ),
    AttackArchetype.ADVERSARIAL_CAMOUFLAGE: ScenarioSpec(
        AttackArchetype.ADVERSARIAL_CAMOUFLAGE,
        "J",
        "Fraud members mix attack payments with legitimate-looking camouflage activity.",
        0.60,
        "camouflage",
    ),
}


def scenario_specs(archetypes: tuple[AttackArchetype, ...]) -> tuple[ScenarioSpec, ...]:
    """Return validated catalog entries in the caller's requested order."""

    return tuple(SCENARIO_CATALOG[archetype] for archetype in archetypes)
