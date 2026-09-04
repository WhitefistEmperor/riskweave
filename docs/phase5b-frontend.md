# Phase 5B — analyst frontend V2

Verified locally on 2026-09-04. Baseline: `80ef03be3e78c86ec7f034b8b9a96cd880e65d49`.
Phase 5B is complete; Phase 5C has not started. This is not public-production approval.

## 1. Frontend audit

The previous primary route was the synthetic replay. Persisted investigations had a minimal link bar,
large record cards and upload controls above completed findings. Evidence was available but the
persisted workflow had no graph. Successful HTTP responses were trusted without checking their shape.
The original eight browser regressions and existing backend architecture were retained. See
[the incremental audit](phase5b-audit.md) for milestone checks and issues encountered.

## 2. Information architecture

| Route | Purpose |
|---|---|
| `/` | Redirect to the investigation worklist |
| `/investigations` | Create and reopen owner-scoped investigations |
| `/investigations/[id]?run=…&ring=…&view=…` | Persisted run, selected candidate and Network/Evidence/Timeline/Investigator tab |
| `/demo` | Preserved Phase 4 replay, benchmark and hard-negative reference views |

Breadcrumbs, a consistent sidebar, saved-run selector and URL state support revisit/reload.
Unknown candidates and cross-investigation run URLs are rejected visibly rather than substituted.

## 3. Visual system

One restrained slate/blue analyst theme in `frontend/app/product.css`, with compact tables, consistent
panel headings, readable status badges, explicit text labels and focused primary actions. Existing
shadcn/Base UI Sidebar, Button, Input, Select, Tabs, Accordion, Table and Skeleton components were reused.
The Sites skill guided local preview/visual inspection and reuse of the installed scaffold; no hosting,
image-generation work, replacement framework or new package was introduced.

## 4. Investigation workflow

Creation is ready only after the initial list load, fixing an observed pre-hydration input race.
The uploader explicitly requires complete DatasetBundle JSON, shows validated artifacts and byte counts,
and exposes checksum provenance. The server remains responsible for validation and duplicate uploads.
Start requests are guarded against overlap. Ambiguous in-page retries reuse the same idempotency key.
Queued/running/completed/failed are real server states, with no fabricated percentage progress.
Polling is aborted on navigation, resumes from persisted state, and stops at terminal states.
Completed results take precedence over collapsed dataset setup. Run provenance remains inspectable.

## 5. Findings experience

The overview shows actual event/entity/candidate counts and the unchanged threshold. Candidates are
sorted by descending existing model score, with deterministic ID tie-breaking. Eight rows per page show
customers, events, observed sharing and existing per-candidate exposure. Opening a row scrolls and moves
keyboard focus into its explorer. Scores are uncalibrated model outputs, never fraud probabilities.
No aggregate exposure is fabricated across potentially overlapping candidates.

## 6. Ring Explorer

The new persisted graph is an explicitly disclosed projection of existing evidence queries. It draws
only query-provided customer/resource, customer/merchant and merchant/payout pairs. Unlinked reported
members remain unlinked; no customer-to-customer shortcut or missing relationship is inferred. No
per-edge event count is fabricated from resource-level totals.

Node shapes/colors and a legend distinguish entity types. Shared resources have an outline; payout
arrows are dashed. Nodes and edges are selectable by canvas or keyboard-accessible selectors. The
details panel exposes full IDs, observed relationships and a link to the exact source evidence.
Pan, zoom, fit, reset, focus and height controls are available. Layout spacing includes labels; shorter
labels plus larger text resolved crowding seen in review. These are display changes, not graph semantics.

## 7. Evidence and timeline

All 13 existing evidence queries remain available, grouped into shared infrastructure, members/commerce,
money/refunds and activity/detector output. Tables paginate at 25 rows. IDs can be expanded with the
keyboard rather than relying on hover. Graph source actions open the corresponding evidence group.
The timeline sorts by timestamp and event ID, shows UTC, payments/refunds, amounts and status, and
provides event details and computed hourly buckets. It explicitly makes no live early-warning claim.
Exposure definitions and values come from the unchanged service. Money displays retain the existing
nearest-rupee presentation; serialized values remain in minor units and investigator facts may include paisa.

## 8. Grounded investigator

The existing investigator endpoint and fact-selection constraints are unchanged. It is scoped to the
selected `(run_id, candidate_id)`. The UI distinguishes deterministic fallback, disabled LLM and optional
extractive-provider modes. Statements retain source query/path citations, and clicking a citation opens
its source. Request overlap, stale completion after unmount and malformed response rendering are guarded.
Unsupported questions and provider warnings remain visible. No free-form evidence is invented by the UI.
Live paid-provider availability was not tested; deterministic execution was real, while provider failure
and malformed-provider replies were explicit transport fixtures.

## 9. Failure, empty and loading states

Explicit views cover empty investigations, no runs, no findings, missing evidence, unavailable session/API,
401, 404/stale run, cross-investigation run, stale candidate, 413/422 upload, failed/timeout run, malformed
JSON/response shapes, failed polling and investigator/provider failure. Errors retain request IDs;
unexpected 5xx response text is not exposed as a server traceback. Final review added validation of
nullable run error/provenance fields so an object cannot crash the error UI. Skeletons indicate reads,
not fake progress. Recovery reads do not silently create a new run.

## 10. Accessibility and responsive verification

Keyboard/overflow tests passed at 1440, 1280, 1024 and 768 pixels, including all four tabs, skip link,
focus transfer, entity selection, graph height controls and sidebar toggle under reduced-motion settings.
Actual-data screenshots were also captured at all four widths with no document overflow. Tables use
contained horizontal scrolling when needed; the inspector stacks below the graph on narrower screens.
The existing 390px demo-navigation test remains green. This is basic keyboard/visual verification,
not a claim of a complete WCAG audit or full assistive-technology compatibility certification.

## 11. Performance and frontend boundaries

- Worklist pages contain ten records; only their histories are read. Full analysis payloads are not loaded for list summaries.
- Candidate pages contain eight rows; event/evidence tables contain 25 rows per page.
- Terminal polling no longer performs a redundant run read. Tests verify polling cessation and navigation cleanup.
- Cytoscape is lazy-loaded and the projection memoized by selected evidence; selection does not rebuild the graph.
- `lib/client.ts` owns transport, `lib/platform-api.ts` / `lib/evidence.ts` own typed contracts,
  `lib/response-validation.ts` owns response checks, and `hooks/use-investigation.ts` owns lifecycle state.
- No localStorage database, service framework or dependency addition. No large-scale performance benchmark was run.

## 12. Actual checks

| Check | Result |
|---|---|
| `uv run --locked --extra dev pytest -q` | **69 passed**, 2 dependency deprecation warnings, 78.16 seconds |
| `uv run --locked --extra dev ruff check .` | **All checks passed** |
| `npm test` against the built production preview | **24 passed**, 1.8 minutes |
| Frontend test breakdown | **21 browser/E2E + 3 pure projection/order/contract tests**; all original 8 retained |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed; existing scaffold exclusions unchanged |
| `npm run build` | Passed; production preview started and exercised |
| `git diff --check` | Passed |
| Packaging | Not rerun in Phase 5B; backend/package inputs unchanged |

The final full browser suite includes real malformed-upload rejection, generated sample analysis,
navigation while active, saved-list revisit, graph nodes/edges, source evidence, timeline reload and
grounded citations. Rare error and zero-result states use clearly identified transport fixtures.
No benchmark results were generated by these UI fixtures. The full suite passed again after the final
malformed-run validation fix. An earlier targeted command was stopped because it was still testing the
previous production build; the subsequent rebuild/full-suite result above is the final result.

Two Python warnings concern Starlette/httpx and an anyio alias. Vinext reports existing JSON import,
external rewrite and route-classification notices. Cancelled browser/RSC requests can produce
`ERR_STREAM_UNABLE_TO_PIPE` in the Vinext server log; no page error occurred in the clean-browser
walkthrough. These upstream/runtime caveats are not presented as a deployment approval.

## 13. Benchmark integrity

`results/phase3/phase3_results.json` SHA-256, rechecked after final code changes:

```text
42c0234331f2b467ccc296f6579478d2feaf7c71e9c159387b6674a09b27e976
```

Unchanged from the required baseline. Git comparison shows no changes to backend source, Python tests,
measured results, Python manifests/lockfile or frontend dependency manifests/lockfile. No detection,
generator, feature, threshold, scoring, candidate or exposure calculation was changed.

## 14. Browser and screenshot review

A clean Chromium session completed creation, real malformed/valid uploads, asynchronous analysis,
navigation during execution, completion, candidate selection, graph/entity/edge/source inspection,
timeline, deterministic investigator, citation opening, list revisit and reload. The walkthrough sample
actually produced **1,021 events, 2,824 entities and 7 candidates**; these are sample output counts, not
new benchmark metrics. It produced zero page errors and no document overflow at the four tested widths.

Reviewed local captures in ignored `outputs/`: worklist, empty worklist, validated upload, queued/active
run, completed findings, selected graph, grouped evidence, timeline/event details, grounded investigator,
real malformed-upload error, zero findings and timeout failure. Empty/zero/failure captures use UI fixtures;
the normal workflow and malformed-upload rejection use the real API. Additional graph captures cover
1440/1280/1024/768px. Screenshots, datasets and recordings are deliberately not committed.

## 15. Backend changes

**None.** No endpoints, models, storage, queue, ownership rules, authentication, detector or benchmark
were changed. Documentation was updated to explain the frontend route migration.

## 16. Remaining UX limitations

DatasetBundle JSON is the only supported input; the model remains synthetic-trained and uncalibrated.
The evidence projection is intentionally incomplete where the API provides no relationship. Dense large
graphs still need zoom/focus and have not been production-scale load-tested. Narrow tables scroll locally.
The worklist shows latest-run status rather than downloading result bodies for aggregate summaries.
Investigator replies are regenerated on request, not a persisted chat log. An ambiguous enqueue key is
retained for retries in the current page session; reload relies on persisted run state and backend duplicate
prevention. There is no claim of live paid-provider, cross-browser or exhaustive screen-reader validation.

## 17. Phase 5C handoff — not implemented

Keep the existing deployment gates: real production identity/authorization integration; dependency audit
and runtime review; actual container/PostgreSQL execution; staging/TLS/reverse-proxy validation; operational
backup/restore, quotas and monitoring appropriate to the next approved scope. No production authentication,
public hosting, TLS, staging, cloud storage, distributed workers or Kubernetes was started here.

## 18. Git checkpoints

Branch: `phase5b-frontend-v2`.

| Checkpoint | Commit |
|---|---|
| Product shell and investigation-first navigation | `75b6fb2` |
| Worklist and resilient lifecycle | `17e230c` |
| Ranked findings and candidate navigation | `5698675` |
| Evidence graph and retrospective timeline | `a3a3016` |
| Grounded investigator and recovery states | `6fa0efc` |
| Final responsive/regression/documentation milestone | Commit containing this report; resolve with `git rev-parse HEAD` at handoff |

The user-facing local `outputs/PHASE5B_REPORT.md` records the final full hash after commit. Only source,
tests, ignore rules and documentation belong in the checkpoint. Local outputs and generated artifacts remain ignored.
