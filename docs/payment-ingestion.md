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
This restriction also applies to synthetic uploads. New result artifacts record the
single event currency. Findings, timeline, nested evidence and investigator sources
use that currency; the browser uses its supported ISO currency precision through
`Intl.NumberFormat`. Fractional units are retained. Unrecognized currencies and old
result artifacts without currency metadata show original minor units, without an
invented scale or default INR label. Investigator statements always preserve minor
units exactly. Existing result files and checksums are not rewritten.
Codes with no ISO minor unit (such as gold/XAU) also retain original units. The
exclusion list follows SIX's current List One, published 2026-09-17; changes to
currency standards require release review.

References: [ECMA-402 currency digits](https://tc39.es/ecma402/#sec-currencydigits),
[SIX ISO 4217 maintenance data](https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html).

The model's amount features were trained on synthetic INR records. Another currency
can be ingested for evidence analysis, but its score distribution is explicitly
unvalidated. Displaying a currency correctly is not FX normalization or model validation.

This contract has no labels, fraud rings, generator seed or synthetic manifest.
Unknown outcomes are not converted into benign labels. Uploaded outcomes never
train the detector. The same causal features, synthetic-trained model and computed
evidence apply; support for observed records does not demonstrate real-data accuracy.

Upload bytes remain checksummed and immutable. Source metadata records the contract
and whether label metadata was supplied. The worker independently parses and validates
the stored bytes after checking their checksum. Explicit offline CSV mapping is available; see [CSV payment mapping](csv-payment-mapping.md).
Provider-specific semantics and missing source features still require review.
