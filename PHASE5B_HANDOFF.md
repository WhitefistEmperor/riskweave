# Phase 5B handoff

Phase 5B is complete. **Do not start Phase 5C without a new user request.**

## Current state

- Branch: `phase5b-frontend-v2`, based on Phase 5A `80ef03b`.
- Six tested milestones: shell/design system; worklist/lifecycle; ranked findings; graph/evidence/timeline;
  grounded investigator/recovery; final responsive/regression/documentation.
- No incomplete source work or known failing test remains.
- Backend, models, generator and frozen benchmark were not modified.
- Final checkpoint is the commit containing this handoff (`git rev-parse HEAD`). Detailed report:
  [docs/phase5b-frontend.md](docs/phase5b-frontend.md). Full final hash is also in local `outputs/PHASE5B_REPORT.md`.

## Verification

- Python: 69 passed, 2 dependency warnings, 78.16s. Ruff passed.
- Frontend: TypeScript and Oxlint passed. Production build passed and served locally.
- Playwright: 24 passed against production preview, 1.8m; original eight retained.
- Keyboard/overflow: 1440, 1280, 1024, 768px; original demo mobile test at 390px retained.
- Real clean-browser workflow and screenshot inspection complete; uncommon zero/failure states were explicit UI fixtures.
- Frozen SHA-256: `42c0234331f2b467ccc296f6579478d2feaf7c71e9c159387b6674a09b27e976`.

## Local preview

Primary UI: `http://127.0.0.1:5173/investigations`; separate replay: `/demo`.
API: `http://127.0.0.1:8000`; readiness: `/api/v1/ready`.
The session used `sqlite:///./work/phase5a-local.db`, storage `work/phase5a-storage`, deterministic investigator.
These persisted files were preserved. Normal repository defaults instead use `work/ringsentinel.db` and
`work/storage`; use the same configuration to revisit the current local records.

For a fresh local instance: run the locked dependency setup and explicit migration from README, then the API;
from `frontend`, run `npm ci`, `npm run build`, `npm start`. Do not run dev and production previews on the same port.
No secret or external provider key is needed for deterministic mode. Generated samples and screenshots are ignored.

## Known limitations and next approved work

DatasetBundle-only input; synthetic-trained scores; partial evidence graph; large-graph performance not
load-tested; no persistent chat history; basic keyboard/visual checks rather than exhaustive accessibility
certification. Existing Vinext notices/cancelled-request log noise and dependency/deployment gates remain.
Container/PostgreSQL, live production auth/provider, TLS/staging/backups/quotas/monitoring require a separately
authorized next phase. Packaging was not rerun because no packaging inputs changed. Do not infer deployment readiness.
