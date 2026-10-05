# Candidate pages and section fragments

Apply migration 0010 explicitly with stopped writers before starting this source.
It adds an index for candidate ordinal range queries; migration 0009 remains the
section metadata foundation. Original result bytes/checksums and existing routes
remain compatible. New completed runs use the immutable section index; legacy runs
retain verified whole-result fallback until explicit stopped-writer indexing.

Owner-authenticated endpoints:

```text
GET /api/v1/runs/{run_id}/overview
GET /api/v1/runs/{run_id}/candidate-page?offset=0&limit=50
GET /api/v1/runs/{run_id}/rings/{candidate_id}/sections/candidate/manifest
GET /api/v1/runs/{run_id}/rings/{candidate_id}/sections/candidate/chunks/{index}
GET /api/v1/runs/{run_id}/rings/{candidate_id}/sections/evidence/manifest
GET /api/v1/runs/{run_id}/rings/{candidate_id}/sections/evidence/chunks/{index}
```

A candidate page returns schema_version, run_id, result_sha256, offset, limit,
total, next_offset and items. Limit is 1–100 (default 50); offsets are nonnegative.
Indexed pages query only their ordinal interval and read only those summaries.
A terminal page has next_offset=null; offsets beyond total return an empty page.
Run ownership is checked before metadata lookup; another owner sees 404. Run
results are immutable, so a result checksum identifies the same order across pages.

Section manifests return schema_version, run_id, candidate_id, section,
result_sha256, sha256 (complete section), encoding=base64,
content_type=application/json, size_bytes, chunk_bytes=2000000 and chunk_count.
Each chunk returns the same scope, index, size_bytes, result_sha256,
section_sha256, sha256 (chunk), and base64 data. Missing/out-of-range indices are
404 after ownership checks; invalid sections are rejected by the API contract.

For indexed runs, neither manifest nor chunk assembles the complete selected
section. A requested 2 MB section chunk can cross two original result fragments.
The server reads each containing fragment through bounded ranges and verifies its
stored SHA-256 before extracting the slice. This may read adjacent data internally,
but does not return it. No new evidence copies or uploaded executable artifacts
are introduced. PostgreSQL server substring/decompression costs are not measured.

Clients must validate matching run/candidate/section/result/section hashes and
indices on every response, strictly decode base64, verify every chunk checksum and
length, reconstruct the advertised order/size, and verify the complete section
SHA-256 before parsing or publishing evidence. A manifest probes the first chunk;
it is not a certificate that every later chunk is intact. Wrong full-section
metadata must be caught by the final reconstruction check. Request cancellation,
owner changes and failures must discard incomplete evidence. Candidate summary
fragments require the reconstructed candidate_id to match the requested one.

Generated tests cover both storage modes, actual HTTP contracts, multiple pages,
Unicode, cross-source-fragment boundaries, evidence exceeding 2 MB, complete
section digest reconstruction, owner isolation, invalid indices, corruption and
legacy fallback. Whole-object and whole-section reads are disabled during the
indexed fragment test. Actual PostgreSQL encrypted restore drills also exercise
candidate pages and section fragments after restoring audit history.

The console requests an owner-scoped overview, then candidate pages of eight items
and only the selected candidate/evidence sections. New results index the overview
scalars in their original immutable bytes. Older indexed results without scalar
metadata use the verified whole-result server fallback for overview; an unavailable
API overview route (404) falls back to the older console transport. Integrity and
other HTTP errors do not trigger fallback. Changing selection/run or unmounting
aborts requests; incomplete/stale evidence is never published. Byte progress reports
verified evidence chunks; graph and review appear only after final section checks.
Graph loading remains lazy. Existing review, evidence, timeline and investigator
components remain available for the verified selection.

Remaining release work:
Pages limit count rather than total response bytes: a single unusually large
candidate summary should use its fragment endpoint. Existing complete evidence
and investigator paths can still assemble a selected large section. Measure
selected-section, browser and provider memory, response limits and concurrency;
these APIs alone do not close the deployed capacity gate.
