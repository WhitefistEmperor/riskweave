# Targeted immutable result sections

Migration 0009 adds result_sections and a nullable versioned candidate_index marker
on analysis_runs. Stop all writers and apply ringsentinel-migrate explicitly before
starting this source. Existing bytes, checksums and review decisions remain unchanged.
New completed runs atomically persist byte offsets, sizes, original ordering and
SHA-256 digests for candidate summaries, query evidence and optional currency.
No evidence payload is duplicated. Each recorded offset is verified against the
unchanged canonical result bytes before commit. Failed persistence rolls back the
index/result metadata and removes caller-owned uncommitted local objects.

Candidate listing reads candidate summaries only. Candidate and evidence endpoints
read their selected section. The investigator receives only selected candidate
queries and currency. Review membership verifies that candidate's summary range,
avoiding a full-result read. Owner authorization happens before index lookup; another
owner sees NOT_FOUND. Missing candidate rows contradicting the committed count,
invalid markers/ranges and checksum failures fail closed. Each storage read is at
most 2 MB, including native database substring reads and local seeks; complete
selected sections are assembled and parsed only after verifying their SHA-256.
Deletion cascades the index with its run; database snapshots preserve it.

A null marker identifies legacy results. Their compatible path retains whole-result
checksum verification. Use private explicit stopped-writer maintenance to enable
section reads without changing the stored result:

```text
uv run --locked python -m ringsentinel.platform.result_sections --writers-stopped --limit 100
```

The command requires an existing fully migrated database, rejects any queued/running
analysis, checks the original result checksum and canonical offsets, and indexes a
bounded batch. Valid older candidate totals are populated. Results without a valid
unique-candidate structure are skipped, preserving their fallback. A nonnull marker
with missing metadata is not silently downgraded to fallback. Repeat for remaining
legacy batches; existing indexes are preserved. The command never migrates implicitly
or prints identifiers/evidence/operator errors.

Verification uses generated results containing large unrelated fields, nested rings
decoys, Unicode and a selected evidence section exceeding 2 MB, with whole-object
reads disabled. Both storage modes cover owner isolation, review writes, range
checksum corruption, missing rows, rollback, legacy maintenance and active-job refusal.
Actual PostgreSQL restore additionally checks targeted candidate reads and restored
review history with full reads disabled.

Limits remain: the selected section is assembled in memory; a single huge evidence
section can still be large. Listing returns all candidate summaries and needs a
future pagination contract. Individual evidence responses do not yet have fragment
transport, and browser complete-result assembly remains unchanged. This implementation
removes unrelated-result reads; it does not prove hosted memory, response or PostgreSQL
server decompression bounds. Do not claim the large-case release gate closed until
those remaining contracts and actual provider measurements are verified.
