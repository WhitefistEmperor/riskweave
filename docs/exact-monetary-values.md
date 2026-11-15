# Exact monetary values

Persisted v1 response contracts now serialize these integer fields as nonnegative
canonical decimal strings: amount_minor, estimated_exposure_minor,
refund_amount_minor and total_amount_minor. This applies to queue/candidate pages,
individual candidates, evidence and inline results, including nested objects.
Clients expecting JSON numbers must adopt strings before upgrading the API.
Counts, scores, ratios and descriptive mean_amount_minor remain numeric.

Python calculation and original saved result bytes remain integer based. No
database migration, result rewrite, model retraining or checksum change is needed.
Section and whole-result fragments intentionally preserve original JSON bytes;
the browser verifies their hashes before decoding with pinned lossless-json 4.3.1.
Its reviver retains monetary source tokens for contract validation. Fractions,
exponent notation, negative amounts, leading zeros and already-rounded unsafe
JavaScript numbers are rejected. Safe legacy integer values remain compatible.

Currency formatting uses BigInt quotient/remainder and Intl formatToParts for
grouping and currency placement, without converting the exact amount to a float.
Currency minor-unit scales are preserved; unknown/unscaled currencies show raw
minor units. Descriptive means are explicitly displayed as approximate minor units.
An exact display does not establish model accuracy or confirmed financial loss.

Coverage includes totals beyond 2^53, signed-64-bit event sizes, a 27-digit
aggregate, USD/INR/JPY/KWD scales, legacy inline integer JSON, original full-result
fragments and selected candidate/evidence fragments. HTTP tests run against both
local and database object stores, preserve original result/section hashes, forbid
whole-object queue reads and retain owner isolation. Existing scalar range size
limits and accepted input/capacity bounds remain; this does not establish hosted
worst-case memory, latency or arbitrary-length input support.

The parser contract follows the package's custom number parser and reviver API:
[lossless-json 4.3.1](https://github.com/josdejong/lossless-json/tree/v4.3.1).
