# ADR 0001: relational ownership, artifact results, and a single local executor

Status: accepted for Phase 5A; deliberately limited to a local foundation.

## Context

The Phase 4 console uses a deterministic synthetic-demo runtime. A revisitable investigation product
needs owned inputs and historical runs without changing the validated detector or moving long analyses
into HTTP request handlers. The hackathon deadline does not justify a distributed infrastructure stack.

## Decision

Use SQLAlchemy with explicit Alembic migrations for User, Investigation, Artifact, and AnalysisRun.
Use SQLite for easy local setup and portable mappings plus psycopg for a PostgreSQL target. Startup
does not create or alter tables. Owner-scoped service operations are mandatory for all resource access.

Store input and completed evidence/result JSON through `StorageBackend`, with relational references
and checksums. Keep large computed evidence out of many new SQL tables. Candidate identity is scoped
to an analysis run; historical results are not overwritten by retries or new analyses.

Expose enqueue/poll/result contracts through typed `/api/v1` routes. A single database-backed scheduler
claims one run and starts one killable Python subprocess. Timeouts and interrupted work become explicit
failed run records. Database constraints prevent simultaneous active runs per investigation; caller
idempotency keys prevent accidental repeated enqueue. There is no automatic analysis retry.

Use a replaceable principal dependency and a development-only header/default principal now. Service
authorization is real owner scoping; the local header is not real authentication. Production settings
reject development identity and protected routes fail closed until a verified identity adapter exists.

Preserve the Phase 3 analysis/evidence behavior and Phase 4 demo as separate concerns. An optional LLM
selects only IDs from computed facts; it never writes detection results or becomes evidence authority.

## Consequences

- Phase 5B can change UI/navigation without inventing another backend lifecycle, auth scope, or result
  transport. Existing demo routes continue to work while new product flows use v1 contracts.
- A new storage/queue/identity adapter can replace local implementations, but production guarantees
  require implementation and testing; interfaces alone do not make this distributed or secure.
- Exactly one API worker/replica is supported with the local executor. API shutdown interrupts the
  active child; restart marks running records interrupted and preserves queued work.
- Files and SQL do not share a transaction. Best-effort rollback cleanup does not solve crash orphan
  collection, power-loss durability, or backup/restore. Those are explicit later hardening tasks.
- PostgreSQL and containers require runtime validation on a capable host; mapping portability is not
  proof of their behavior. The default production image is intentionally unusable for protected user
  flows until real authentication is configured through a future adapter.
- The input remains a synthetic DatasetBundle and the model remains synthetic-trained/uncalibrated.
  No real-payment generalization or improved benchmark result is claimed by this architecture work.

## Alternatives not selected

An in-memory-only store cannot preserve investigation history. Synchronous HTTP analysis has fragile
timeout/retry semantics. Redis/Celery and cloud storage add operational scope without improving this
deadline's validation. Globally shared resources or a public development header would discard the
ownership boundary. Splitting every evidence field into relational tables would add migrations and
duplication without a present query need.

See [the architecture document](../PRODUCTION_ARCHITECTURE.md) for concrete contracts, migration and
startup commands, current limits, and Phase 5C deployment gates.
