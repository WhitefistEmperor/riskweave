# Indexed result delivery

Migration `0007` adds result size and per-fragment SHA-256 metadata. New completed
runs persist this metadata in the same transaction as their result reference.
Payload bytes are not duplicated. Case deletion cascades to fragment metadata.

Every manifest and fragment request authorizes the case owner. An indexed
manifest validates metadata and probes the first fragment only; it does not
certify all stored bytes. Each requested fragment reads at most 2,000,000 bytes
and checks its saved digest. The browser verifies every fragment and the full
reconstructed checksum before displaying findings. Missing or corrupt indices
fail closed rather than silently switching to a full-object read.

Local storage seeks to the requested range. Database storage selects a binary
substring and size metadata, avoiding full payload transfer into the API process.
Database decompression/server CPU, actual hosted memory and throughput still need
measurement. Analysis serialization, legacy projection endpoints and complete
browser reconstruction still allocate full results; this change does not establish
an end-to-end capacity guarantee.

## Existing results

Existing rows keep a null result-size marker and retain the original verified
whole-object transport. Migration does not rewrite existing payloads. To index
these results during a maintenance window:

1. Stop API writers, local executors and remote workflow writers. Do not submit
   new analysis until maintenance is complete.
2. Back up the database and matching object storage. Apply migrations explicitly
   with `python -m ringsentinel.platform.database` using the intended environment.
3. Run `python -m ringsentinel.platform.result_fragments --writers-stopped --limit 100`.
   Repeat bounded batches until the returned count is zero.
4. Restart writers and verify readiness and complete result reconstruction.

The command requires an existing database at the current migration and refuses
queued/running analysis. The flag is an operator acknowledgement; it does not
stop services itself. Each result is read and checked against its existing whole
checksum before a transactional metadata-only update. Corrupt payloads or partial
pre-existing indices abort the affected transaction. Earlier successful batches
remain committed; retrying skips indexed results. Payloads and whole checksums
remain unchanged, but ORM update timestamps may advance. The command exposes only
an aggregate count or a sanitized failure code, not case IDs or data.

## Verification

Integration tests cover both storage modes: bounded range reads with full reads
forbidden, exact reconstruction, later-fragment corruption, incomplete metadata,
owner isolation, cascading deletion, explicit/idempotent maintenance and refusal
of active work or corrupt legacy objects. The PostgreSQL 17 backup drill restores
a multipart result and verifies range reads with whole-object reads forbidden.
