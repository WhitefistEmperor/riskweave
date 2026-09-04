# RiskWeave analyst console

React/TypeScript, Vinext, Tailwind/shadcn, and Cytoscape. The root route opens the
persisted investigation worklist; `/demo` is the separate synthetic replay workspace.

Follow the repository's [quick start](../docs/quick-start.md) for backend installation,
migrations, a sample upload, frontend startup, browser dependencies, and production-preview
commands. No hosted service or paid model key is required for the default local workflow.

From this directory, with the backend already running:

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Browser API requests use the same-origin proxy to FastAPI.
Do not expose the development server or development identity publicly.

## Checks

```sh
npx playwright install chromium
npm test
npm run lint
npm run typecheck
npm run build
```

`npm test` needs both local servers running with demo enabled and the default deterministic
investigator. It includes real upload/analysis/evidence/revisit checks and explicitly labeled
rare-state transport fixtures. Set `RINGSENTINEL_UI_URL` to use a different local frontend URL.
Generated test screenshots remain ignored; curated submission captures are in
[the gallery](../docs/assets/screenshots/README.md).

Application code is linted. The unchanged bundled `components/ui` catalog and
`hooks/use-mobile.ts` remain excluded from Oxlint for upstream scaffold findings;
all TypeScript is typechecked. Latest measured checks and dated audits are in
[submission validation](../docs/submission-validation.md), not a live CI status badge.

## Code map

- `lib/client.ts`: shared transport; `lib/platform-api.ts` and `lib/evidence.ts`: contracts.
- `lib/response-validation.ts`: runtime response checks.
- `hooks/use-investigation.ts`: server-backed investigation lifecycle.
- `components/`: worklist, run setup, findings, network, timeline, and investigator views.

The evidence graph renders query-provided relationships only; it never fills missing edges.
Scores are uncalibrated and sharing alone is not proof of abuse. See the
[Phase 5B frontend notes](../docs/phase5b-frontend.md) for implementation history and
[Phase 5C gates](../docs/phase5c-final.md) for unresolved production risks.
