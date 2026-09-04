# Historical replay demo — three to five minutes

This is the original Phase 4 **synthetic replay** walkthrough, retained for the separate
`/demo` route. The primary product now opens persisted investigations. For the submission
recording, use the current [2–4 minute demo script](../DEMO_SCRIPT.md) and
[local setup](quick-start.md). Replay timing claims below describe one example, not the
retrospective uploaded-dataset workflow or average detection latency.

## Before presenting

Install once with `uv sync --extra dev` and `cd frontend; npm ci` (run commands
on separate lines if preferred). Start `uv run ringsentinel-api` in the repository
root and `npm run dev` inside `frontend`. Open http://127.0.0.1:5173 and wait for
the actual data to load, then open `/demo`. No API key is needed. Keep the API terminal running.
Do not start a second process on an occupied port; stop the existing one with Ctrl+C.

For stable presentation without hot reload, `npm run build` then `npm start`
replaces the frontend dev server on the same port. Do not edit source mid-demo.

## Script

1. **0:00–0:30 — Problem and baseline.** “Individually ordinary transactions can
   belong to a coordinated ring. Our benchmark deliberately overlaps their amounts
   and account ages.” Show the actual transaction/network PR-AUC comparison.
2. **0:30–1:20 — Replay.** Click Reset, then Start replay at 1×. The compact window
   contains 104 actual events; UI speed accelerates gaps, never changes timestamps.
   Disclose the earlier isolated alert: an event crossed threshold before this
   window but did not form a candidate. Attack activation is labeled demo truth,
   not a model input. The focus attack begins Jan 3, 14:06:16 UTC. Candidate evidence
   first qualifies at 14:14:16: eight minutes later. This is one example, not average.
3. **1:20–2:10 — Evidence.** Click Open Ring Explorer when the candidate appears.
   It pauses the replay and opens only observed prefix evidence. At first detection
   there are two linked events/two customers. Select a shared device/IP, focus it,
   fit the graph, expand a sharing query, then open Activity timeline. Distinguish
   the first suspicious event from the first connected precursor. Mention that
   candidate IDs change as membership grows; they are not persistent case IDs.
4. **2:10–2:50 — Investigator and exposure.** Ask “Why was this ring flagged?”
   Open a citation's source. Default mode is visibly “deterministic evidence fallback,”
   not a hidden LLM. Ask about financial exposure; purchases/refunds are counted once.
   Optional LLM assistance only selects/orders computed facts, never decides fraud.
5. **2:50–3:30 — Benchmark.** Show PR-AUC 0.199 vs 0.971, event recall/F1, and 100%
   ring detection on the measured synthetic benchmark. Show the graph heuristic's
   weaker performance and family ablations. Expose the 8.14% exposure error and 4.44%
   aggregate underestimation. Do not describe scores as calibrated probabilities.
6. **3:30–4:15 — Hard negative.** Select hostel or family. The real graph rule flags
   the dense legitimate group; the network-aware model does not. “Sharing alone
   is insufficient.” This is an observed comparison, not a causal proof of why the
   model made this individual prediction.
7. **4:15–4:30 — Limitations.** Synthetic validation, unknown distribution shift,
   merchant-collusion variability, uncalibrated scores. Production needs retraining
   and monitoring. Stop here; do not imply production readiness.

## Recovery

- Backend unavailable: confirm port 8000 and run the backend command; click Retry.
- Cold start: allow about 20–40 seconds. Warm the overview before judges arrive.
- Optional provider unavailable: visible deterministic fallback remains functional.
- Replay finished: Reset or Start replay begins the same deterministic window again.
- Wrong Explorer scope: sidebar = completed ecosystem; live watch = current prefix.
- Repeated dependency installation is unnecessary. Use the checked-in lockfiles.
