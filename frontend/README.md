# RingSentinel console

Local React/TypeScript analyst application using the Sites/Vinext scaffold and
bundled shadcn UI components. No hosted service is required.

From the repository root, run `uv sync --locked --extra dev`, `uv run ringsentinel-migrate`, then `uv run ringsentinel-api`.
In another terminal: `cd frontend`, `npm ci`, then `npm run dev`.
Open http://127.0.0.1:5173. The root redirects to the persisted investigation worklist.
Create an investigation, upload a complete DatasetBundle JSON, start analysis and review the saved findings.
Generate a sample with `uv run python scripts/make_upload_sample.py --output work/sample.json --transactions 1000 --seed 105` from the repository root.

For production-preview mode, stop the dev server, run `npm run build`, then
`npm start`. The Next-compatible rewrite forwards API requests to the same backend.
No Cloudflare account or deployment is needed. The Python source distribution is
backend-only; use the repository checkout for the frontend source and lockfile.

Checks: `npm run lint`, `npm run typecheck`, `npm run build`.
Application code is linted. The unchanged bundled `components/ui` catalog and
`hooks/use-mobile.ts` are excluded from Oxlint because the scaffold has upstream
accessibility/compiler lint findings; all TypeScript is still typechecked.

The separate `/demo` route contains the payment feed and chronological observed-prefix snapshots.
Risk scores are uncalibrated; benchmark values come from measured Phase 3 artifacts.
UI playback accelerates event gaps without changing the original UTC timestamps.

`npm test` runs real-data Playwright checks plus explicitly labelled rare-state transport fixtures against the running local servers.
The original eight regressions remain; the persisted happy path now also exercises real malformed-upload rejection,
navigation while analysis is active, graph node/edge inspection, timeline reload, citations and saved-list revisit.
Set `RINGSENTINEL_UI_URL` to test a different local frontend port.
Screenshots go to ignored `../outputs/`; the old Phase 4 curated copies under `docs/screenshots` are historical.

Phase 5B boundaries: `lib/client.ts` is the shared transport; `lib/platform-api.ts` and
`lib/evidence.ts` hold typed contracts; `lib/response-validation.ts` rejects malformed responses;
`hooks/use-investigation.ts` owns server-backed lifecycle. Presentation is split into shell, worklist,
run setup, findings, graph, timeline and investigator. No backend/model/benchmark changes were required.
The evidence graph only projects query-provided pairs, with source links. It never fills missing edges.
Investigation histories, bounded candidate/evidence pages, terminal polling cessation and lazy graph loading
keep the interface lightweight. No new dependency, frontend database, auth provider or hosting was added.

The locked scaffold dependencies have npm audit findings. This is a localhost-only
hackathon app, not a deployment/security approval. Do not expose the dev server.
