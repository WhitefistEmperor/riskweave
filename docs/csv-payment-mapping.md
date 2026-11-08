# Private CSV payment mapping

`python -m ringsentinel.data.csv_mapping` converts two private exports into
uploadable `payments-v1` JSON. This is an offline command, not a CSV upload
endpoint. It never trains the model, invents labels or certifies accuracy.
Keep CSVs, mappings, converted outputs and provenance in ignored private storage.

Copy `schemas/payment-csv-mapping.example.json` and set the source column names
for every canonical field. The example declares synthetic control data; change
`data_origin` according to the actual source. `authorization_confirmed: true` is
an operator declaration, not independently verified permission. Give each reviewed
mapping a distinct `mapping_version`; freeze it before inspecting test outcomes.
The sidecar hashes exact source files, mapping bytes, converted payments and converter
source. Retain it with evaluation reports. Uploads retain canonical payment bytes
and their checksum; the sidecar is not automatically attached to investigations.

The entity CSV requires `entity_id`, `entity_type`, `created_at`. The event CSV
requires all `PaymentEvent` fields except arbitrary metadata, plus `retry_count`.
The example lists all required fields. Each canonical field maps to one unique
source column. Headers must be unique. Additional columns are ignored, including
labels. Arbitrary attributes/metadata are not imported. Never map outcomes or
post-event knowledge into features. Mappings rename columns only and cannot verify
source-column semantics; a provider-specific adapter still needs review.

Use stable pseudonymous identities for customers, merchants, cards, devices, IPs,
addresses and bank accounts, with correctly typed entity records. Supply actual
customer creation times and source retry counts, not guessed values. Conversion
preserves identifiers; it does not anonymize them. Sources without the required
identities/history need a reviewed ingestion adapter. Missing values are rejected.

Amounts must already be positive integer minor units, at most 2^63-1. No decimal
parsing, currency-scale guessing, rounding or FX conversion occurs. Retry counts
are integers from zero through 1,000,000. Timestamps must be ISO strings containing
`T` and an explicit timezone. Enums and currency codes must match the canonical
schema exactly. Only `original_transaction_id` may be blank; refunds require it,
payments must leave it blank. Whitespace is not silently trimmed. Existing validation
checks references/types, duplicates, chronology, refund identity and cumulative
refund amounts, and single-currency isolation.

UTF-8 (optional BOM), quoted fields and comma/semicolon/tab delimiters are supported.
CSV defaults limit each field to 131,072 characters. Each input and canonical output
is limited to 100 MB, each CSV to 100,000 rows. This in-memory offline command does
not establish safe hosted capacity. Output must also fit the deployment's configured
upload budget. Malformed/ragged/blank rows fail; records are not silently skipped.

```powershell
.venv/Scripts/python -m ringsentinel.data.csv_mapping `
  --entities work/private/entities.csv `
  --events work/private/events.csv `
  --mapping work/private/mapping.json `
  --output-directory work/private/converted-v1
```

The output directory must not exist and its parent must exist. Success writes
`payments.json` and `provenance.json`, with sanitized status on stdout. Existing
outputs are never overwritten. Invalid data is rejected before creating outputs.
Write failures attempt cleanup of newly created files; if permissions or storage
failure prevent cleanup, inspect incomplete outputs locally. Never use an incomplete
output pair. Failures exit 2 without source values, paths or validation exceptions.
Converted payments can enter investigation upload or frozen-model evaluation.
Supply resolved labels separately; missing outcomes remain unknown.

Tests verify exact causal-feature preservation, identities/units/refunds, quote/BOM
handling, invalid inputs, bounds, provenance, no overwrite and private failures.
An unchanged pinned-model smoke successfully evaluated a converted synthetic control
with 55 validation and 49 test events. This verifies command compatibility, not
observed-data accuracy. No provider-specific export or observed dataset is validated.
