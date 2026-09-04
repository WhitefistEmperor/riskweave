# Phase 5B frontend audit and implementation plan

Baseline: `80ef03be3e78c86ec7f034b8b9a96cd880e65d49`, clean before work.

## Audit

- `/` is the Phase 4 demo; `/investigations` and `/investigations/[id]?run=…` are persisted workflows. Their shared shell is only a row of links.
- The list uses one large card per record, without a useful review hierarchy. Creation/upload work, but completed results sit below upload/history controls.
- Persisted findings expose query accordions and an investigator, but no graph. The existing Cytoscape explorer is demo-only. Its graph, keyboard node picker, resize handling and evidence rendering are reusable.
- Typed transport is centralized in `lib/client.ts` and `lib/platform-api.ts`; lifecycle/UI state is concentrated in `investigation-workspace.tsx`. Polling aborts on unmount, but redundantly rereads terminal runs. Successful response shapes are not checked.
- Existing primitives include Sidebar, Table, Tabs, Select, Accordion, Skeleton, Input and Button. No dependency additions are needed.
- Eight browser tests cover five genuine demo paths and three persisted/error flows. Retain their behavior; move demo navigation to `/demo` intentionally.
- Inspected the desktop application locally at 1440px. Initial capture is explicitly a loading state, not evidence of an empty database. The current primary screen has excessive unused space and weak hierarchy.

## Protected boundaries

No detector, generator, benchmark, threshold, candidate, exposure or backend API changes. Persisted analysis stays retrospective; prefix-safe replay stays a separate demo. A persisted evidence graph may display only relationships explicitly present in existing query responses, never inferred customer-to-customer links. Scores are not probabilities. Development identity is not production authentication.

## Checkpoint plan

1. Product shell, restrained design tokens, primary investigation navigation; preserve demo route.
2. Investigation list and resilient upload/run lifecycle, centralized response validation.
3. Ranked findings with URL-backed candidate navigation.
4. Evidence-derived graph, grouped evidence and chronological timeline.
5. Grounded investigator and recoverable error states.
6. Responsive/accessibility checks, full regression, screenshots, handoff/report.

Each milestone is checked before committing. Screenshots and generated test data remain ignored local outputs. No Phase 5C work or hosting changes.

## Milestone checks

- Shell: TypeScript, lint and production build passed; existing mobile demo navigation and persisted empty/error tests passed (2/2).
- Lifecycle: TypeScript/lint/build and all three persisted browser flows passed across targeted runs. Real create/upload/analysis/evidence/investigator/reload passed in 26.2s. Fixed an observed pre-hydration input race by keeping creation input disabled until the initial list read finishes. The first restricted run could not access uv's cache; the authorized rerun used the real generator. Terminal polling now returns the terminal record instead of fetching it twice. Source, not backend behavior, changed.
- Findings: TypeScript, lint, production build and real persisted + failed/zero-result regressions passed (2/2, 38.7s). Reviewed the completed-run screenshot: ranked compact rows, actual event/entity counts, uncalibrated-score disclosure, per-candidate exposure, collapsed setup and grouped evidence. Formatted touched TypeScript/CSS with the existing formatter. Added no packages.
- Evidence workspace: graph projection/ordering/contract checks passed (3/3); the expanded real workflow passed (23.6s), including keyboard node/edge selection, source-evidence navigation, event inspection and timeline URL reload. Graph/timeline screenshots had no page errors or document overflow. Visual review found crowded graph labels; enabled label-aware layout spacing. Graph is lazy-loaded, memoized by selected evidence, and uses a resize observer. No per-edge counts or missing relationships are invented. Evidence tables paginate at 25 rows and expose full IDs by keyboard.
