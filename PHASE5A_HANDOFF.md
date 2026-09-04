# Phase 5A handoff — local implementation verified, external gates pending

Do not restart from Phase 4 or discard any existing work. Phase 5B has not started.

## Checkpoints and completed local milestones

- Phase 4 baseline: `722ef7abef6937f3fdf9b34bb13dfa1d0c30709d`.
- Phase 5A domain/migrations: `40f269f7a764320e5b5969227576a717b9c7b958`.
- Safe storage and actual subprocess lifecycle: `2c097a5`.
- Versioned APIs, ownership, safe errors/configuration/provider boundaries: `18baa15`.
- Minimal persisted frontend, typed client, scoped dependency updates: `11daac5`.
- Final operations/documentation checkpoint follows these in `git log`.

The resumed seven untracked files were preserved and incorporated. Regression fixes
prevent storage collision deletion and reject malformed attack-progressions at the
upload boundary. Actual scheduler/subprocess completion, timeout termination,
worker failure, interrupted work, concurrent starts, owner isolation, checksums,
and restart persistence are tested. All original detector/benchmark behavior remains.

## Files and partial work

No source file is half-edited. Source, tests, minimal UI, sample/smoke scripts,
documentation, Docker recipes and CI definitions are saved. Container recipes are
statically validated but **not runtime verified**. `docs/PRODUCTION_ARCHITECTURE.md`
describes current contracts and limits; `docs/phase5a-verification.md` records actual
results. Generated fixtures/database/objects remain ignored under work/, not staged.

## Checks

- 69 Python tests passed; Ruff passed. Two upstream TestClient warnings remain.
- Frontend lint, TypeScript, production build and all 8 browser tests passed.
- Wheel/sdist built; packaged migrations and frozen benchmark verified.
- Fresh/repeated SQLite migration tests passed; real API process restart reopened
  the same result checksum. 1,021-event smoke produced 7 candidates in 16.06 seconds.
- Container/workflow static parsing and local-only topology checks passed.
- No live paid provider request; deterministic and provider-contract tests passed.

## Known external blockers / exact next checks

1. Docker and Podman are absent; WSL is not installed. On a Docker-capable host,
   supply a URL-safe throwaway `RINGSENTINEL_DB_PASSWORD` via the shell, then run
   `docker compose config --quiet`, `docker compose build`, and
   `docker compose up --wait --wait-timeout 180`.
2. Check `/api/v1/health`, `/api/v1/ready`, and the frontend; then run
   `uv run --locked --extra dev python scripts/smoke_platform.py --base-url http://127.0.0.1:8000`.
   Reopen a completed run after a backend restart. Do not remove named volumes.
   This closes the currently unverified PostgreSQL/container completion gate.
3. Retry `npm audit --json --fetch-timeout=30000 --fetch-retries=0` from frontend/.
   The baseline was 11 affected packages. Scoped fixes are installed and browser
   tested, but three post-update advisory requests timed out; remaining count is
   unknown, not zero. Record the actual new result in docs/dependency-audit.md.
4. Run configured CI on a GitHub runner when separately authorized to push. No
   remote CI execution or deployment has occurred in this task.

Do not call Phase 5A fully verified until its container gate passes. Production
identity intentionally fails closed; real authentication, security/deployment
hardening and real-payment ingestion are later work, not hidden completed features.
Do not begin Phase 5B without the user's next instruction.
