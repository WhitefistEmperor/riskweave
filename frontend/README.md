# RingSentinel console

Local React/TypeScript analyst application using the Sites/Vinext scaffold and
bundled shadcn UI components. No hosted service is required.

From the repository root, run `uv sync --extra dev` and `uv run ringsentinel-api`.
In another terminal: `cd frontend`, `npm ci`, then `npm run dev`.
Open http://127.0.0.1:5173. The first API data request reproduces seed 105 locally.

Checks: `npm run lint`, `npm run typecheck`, `npm run build`.
Application code is linted. The unchanged bundled `components/ui` catalog and
`hooks/use-mobile.ts` are excluded from Oxlint because the scaffold has upstream
accessibility/compiler lint findings; all TypeScript is still typechecked.

The payment feed and candidate watch are chronological observed-prefix snapshots.
Risk scores are uncalibrated; benchmark values come from measured Phase 3 artifacts.
UI playback accelerates event gaps without changing the original UTC timestamps.

The locked scaffold dependencies have npm audit findings. This is a localhost-only
hackathon app, not a deployment/security approval. Do not expose the dev server.
