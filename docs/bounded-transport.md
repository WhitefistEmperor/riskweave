# Authenticated upload and result fragments

Migration `0005` adds private upload sessions and parts. Existing inputs, results,
review history and object keys remain intact. Database storage supports staged
uploads; the default filesystem backend retains its existing local upload route.

The console sends files larger than 2,000,000 bytes through these owner-scoped routes:

1. `POST /api/v1/investigations/{id}/uploads` reserves one upload per idle case,
   binding an idempotency key to its filename, byte size and whole-file SHA-256.
2. `PUT /api/v1/investigations/{id}/uploads/{upload_id}/parts/{index}` sends at most
   2,000,000 bytes with `X-Chunk-SHA256`. Streaming counts actual bytes; a declared
   content length is only an early rejection hint. Duplicate identical parts are safe.
3. `POST /api/v1/investigations/{id}/uploads/{upload_id}/complete` checks contiguous
   parts, total size, checksum and the complete dataset contract before accepting an
   artifact. Validation failure aborts the session and releases its bytes and case.

`GET /api/v1/investigations/{id}/uploads` returns pending progress. The console
shows saved parts after an interruption or reload; selecting the same file resumes
missing parts. `DELETE .../uploads/{upload_id}` discards a pending upload. Analysis
and whole-case deletion remain guarded while a reservation is active. Finishing an
upload does not automatically start analysis. Identical completed retries return
the same artifact. All routes authorize ownership; another owner receives 404.

Staged parts and permanent objects share the global storage budget. Assembly replaces
staged bytes with a validated object in one transaction, without charging both copies.
Database mutation locks serialize competing admissions. Pending sessions expire 24
hours after creation; scoped reads/begin operations recover them and remove parts.
No scheduler guarantees prompt expiry cleanup in an idle deployment. Expired or aborted
idempotency keys cannot create a new upload; the console starts a fresh attempt.
Backups refuse unfinished writes, and whole-case erasure includes upload sessions.
Session metadata also has independent admission limits: 100 sessions per case and
10,000 globally by default, including completed/aborted/expired history. Set
`RINGSENTINEL_MAX_UPLOAD_SESSIONS_PER_INVESTIGATION` and
`RINGSENTINEL_MAX_UPLOAD_SESSIONS_TOTAL` to an explicit operational budget.
Existing session retries can continue at that limit; creating another returns quota
exhaustion. Whole-case erasure removes its session history with the case.

Completed request-mode results use `GET /api/v1/runs/{id}/results/manifest` and
`GET .../results/chunks/{index}`. Each fragment contains at most 2,000,000 source
bytes, base64 encoded to approximately 2.67 MB. The client binds the manifest to
the authorized run, case and saved result checksum, checks each fragment, verifies
the complete SHA-256, then decodes UTF-8 and validates JSON before showing findings.
Navigation aborts delivery. No public storage URL, key or bearer token is issued.

The inline `GET /api/v1/runs/{id}/results` route admits at most 2,000,000
stored source bytes. It authorizes the run first, then inspects object size before
reading/deserializing the full result. Larger results return 409 with
`RESULT_TRANSPORT_REQUIRED` and use the existing manifest/chunk routes. Database
size checks compare stored byte metadata with database byte length without
transferring the complete object to the application; filesystem checks use stat.
The console handles this explicit response for older local-mode runs too, binds
fragments to their saved checksum and verifies the complete result before display.
Other errors retain their existing behavior. This changes inline delivery, not
which completed results are retained or admitted by the analysis byte budget.

The application upload/result limits remain unchanged. These routes keep their
request/response bodies below Vercel's 4.5 MB function transport ceiling; this has
been verified locally and in CI, not on a hosted Vercel deployment. The legacy whole
result and evidence APIs remain available and may exceed that ceiling on large
cases. Investigator source responses also require a separate large-case review.

Assembly and browser decoding still allocate the complete file/result in memory.
Migration 0007 indexes new results with per-fragment digests. Indexed requests
read and verify only the requested range (the manifest probes the first part);
legacy results retain whole-object verification until explicit stopped-writer
indexing. See `docs/result-fragment-index.md` for maintenance and integrity semantics.
Database transfer, memory, fragment count and worst-case latency need capacity tests
before a large-workload release. Chunk transport does not provide durable background
analysis dispatch or establish hosted runtime, identity or provider readiness.

The CI request-mode smoke uploads a generated dataset padded beyond 4.5 MB, performs
real pinned-model inference against PostgreSQL, verifies authenticated result fragments,
saves/reloads a review and erases only its own generated investigation. Padding changes
transport size while preserving model input; it is not model accuracy evidence.
