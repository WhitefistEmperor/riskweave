# Unlabeled payment ingestion

The investigation upload accepts two explicit contracts: the existing synthetic
`DatasetBundle`, and an observed payment dataset with this top-level shape:

```json
{"schema_version":"payments-v1","entities":[],"events":[]}
```

Replace the arrays with `EntityRecord` and `PaymentEvent` records from the data
model. Events must be nonempty. Entity IDs must be stable pseudonymous identifiers;
include actual customer creation timestamps because account age is a model feature.
Do not supply card numbers, credentials, or unnecessary personal information.

All event references must resolve to correctly typed entities. Payment transaction
IDs and event IDs must be unique. Refunds must follow their original payment,
match its customer, merchant, card and currency, and cumulatively stay within its
amount. Analyze each currency in a separate dataset; no FX conversion is implied.

This contract has no labels, fraud rings, generator seed or synthetic manifest.
Unknown outcomes are not converted into benign labels. Uploaded outcomes never
train the detector. The same causal features, synthetic-trained model and computed
evidence apply; support for observed records does not demonstrate real-data accuracy.

Upload bytes remain checksummed and immutable. Source metadata records the contract
and whether label metadata was supplied. The worker independently parses and validates
the stored bytes after checking their checksum. Arbitrary CSV mapping is still pending.
