# Targeted immutable result sections

Migration 0009 adds result_sections and a nullable versioned candidate_index marker
on analysis_runs. Migration 0010 adds candidate ordinal indexing. Stop all writers and apply ringsentinel-migrate explicitly before
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

Candidate pages and section fragments are now implemented; see
[candidate section transport](candidate-section-transport.md). Limits remain: direct
selected evidence/investigator reads assemble the section; the console still assembles
complete results. A single huge candidate can exceed a page response budget, so use
its fragment endpoint. Hosted memory, response and PostgreSQL server decompression
bounds still require measurement and browser adoption. Do not claim the large-case
release gate closed solely from these API tests.

## Upgrade older indexed queue metadata

With every API/worker/cron writer stopped and a verified private backup, use:

```text
uv run --locked python -m ringsentinel.platform.result_sections --writers-stopped --upgrade-queue --limit 100
```

This explicitly selects completed runs lacking a true queue_present marker (both
null legacy and older existing indexes). Existing current indexes are skipped.
The batch remains 1–1,000 runs. Any queued/running analysis refuses maintenance.
Original result checksum/size and canonical bytes are verified. Before replacing
an older index, every existing row must match the regenerated original range,
checksum and ordinal; required candidate/evidence/currency/declared overview rows
must exist. Corrupt or incomplete indexes fail rather than being silently repaired.
Complete queue fields are required for older nonnull indexes.

Replacement rows and the marker are committed in the same transaction. Original
result bytes/reference/hash and reviews are preserved. Failure after deleting old
rows rolls back their deletion. Successful upgrades are idempotent; repeat bounded
batches until count=0. CLI output remains aggregate-only and errors sanitized.
The command assembles the original result during offline verification; budget
operator memory accordingly. It never runs automatically during API requests,
migrates schemas or overrides the need to actually stop writers.

Both local storage modes test verified upgrade, rollback after replacing metadata,
corrupt index denial, active-job refusal and whole-read-free upgraded queue output.
The PostgreSQL encrypted restore drill now executes the upgrade before backup and
checks restored bounded summaries; its exact-source CI result must be inspected.
The console now uses bounded queue summaries and selected sections. Hosted and
large selected-evidence/investigator memory remain separate release gates.

The existing local preview was maintained on 5 October 2026 after a verified
standard snapshot and stopped API: 18 legacy indexes upgraded, repeat pass0,
19 completed saved runs verified with whole reads disabled. Original result/
review/audit fingerprints and all other table counts survived. The actual snapshot
also restored into a separate new target with all original fingerprints matching.
See the handoff and aggregate operations report. This does not apply maintenance
to any hosted database or establish encrypted/off-host/scheduled recovery.
