# Phase 1 data model

RingSentinel models payment activity as immutable entities plus temporal events. All identifiers and
attributes are synthetic. Dates are timezone-aware UTC values and money is stored as integer minor units
(paise for INR).

## Entity table

`entities.jsonl` contains `CUSTOMER`, `MERCHANT`, `CARD`, `DEVICE`, `IP`, `BANK_ACCOUNT`, and `ADDRESS`
records. `TRANSACTION` and `REFUND` are reserved entity types: Phase 3 can materialize the corresponding
event records as graph nodes without changing the ground-truth label vocabulary.

Raw entity and event attributes never contain fraud flags, ring identifiers, archetype names, or benign
community labels. Those values live only in the ground-truth files, preventing target leakage in later
experiments.

Each row has:

- `entity_id`: stable synthetic identifier unique within the dataset.
- `entity_type`: heterogeneous node type.
- `created_at`: account or infrastructure creation time.
- `attributes`: deliberately non-sensitive synthetic metadata.

## Event table

`events.jsonl` contains `PAYMENT` and `REFUND` records. Every event carries its customer, merchant, card,
device, IP, address, and merchant payout-bank references. A refund also carries
`original_transaction_id`; validation requires it to follow an existing payment and not exceed the
original amount. `--transactions` controls only the number of `PAYMENT` events, so refunds are additional.

These references define the future graph relationships (`USES`, `CONNECTS_FROM`, `LOCATED_AT`,
`PAID_TO`, `PAYS_OUT_TO`, and `REFUND_OF`) while retaining event timestamps.

## Ground truth

`entity_labels.jsonl` and `event_labels.jsonl` cover every entity and event exactly once. Labels contain a
fraud flag, zero or more ring identifiers, and an optional attack stage. Ring J intentionally contains
related camouflage payments whose event label is benign while the owning entities remain ring members.

`fraud_rings.json` provides one record per injected operation:

- ring archetype and description;
- complete member-entity and related-event identifiers;
- the subset of events that are fraudulent;
- attack start time and ordered progression stages;
- monetary exposure and expected loss.

Monetary exposure counts value once per original payment. A captured fraud payment contributes its
captured amount. If an abusive refund exists, the exposure contribution is instead the total abusive
refund value capped at the original purchase amount; purchase and refund values are never added together.
For refund abuse, setup purchases are related context but only abusive refunds are fraud-labeled.

Expected loss is `round(monetary_exposure_minor * expected_loss_rate)`. Every ring record marks
`expected_loss_rate_kind` as `synthetic_assumption`: these rates are scenario configuration, not calibrated
fraud probabilities or measured model outputs.

`benign_communities.json` identifies deliberate hard negatives: family, office, hostel, campus, shared
Wi-Fi/kiosk, and common-merchant cohorts. Shared infrastructure alone is therefore never a fraud label.
Community sizes vary, and each community can share pools of addresses, networks, devices, or a popular
merchant so simple shared-infrastructure thresholds can produce false positives.

## Benchmark-hardening guarantees

- Raw identifiers are deterministic opaque hashes, not generation-order counters.
- Fraud and benign amounts use overlapping heavy-tailed distributions.
- Fraud and benign customer ages are sampled from the same range.
- Attack start clock times are independently jittered; coordinated timing remains a group behavior rather
  than a target-revealing timestamp convention.
- Benign refunds are present, so the refund event type is not itself a fraud label.
- Raw metadata and attribute shapes are shared across labeled populations.

## Reproducibility and validation

`manifest.json` records the seed, full generator configuration, counts, schema versions, and a canonical
content SHA-256. `checksums.sha256` covers each serialized data file. The validator checks uniqueness,
referential integrity, entity types, refund links and timing, complete label coverage, ordered attack
stages, exposure math, ring membership, hard-negative cleanliness, and manifest counts.
