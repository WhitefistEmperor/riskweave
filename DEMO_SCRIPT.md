# RiskWeave — 3-minute demo script

## Before recording

- Follow [local setup](docs/quick-start.md). Use a clean local presentation workspace and the
  seed-105, 1,000-payment sample. No real customer data or paid provider is needed.
- Rehearse the real upload and analysis once; keep a completed investigation available if
  the recording cannot accommodate cold-start time. Never present prerecorded completion as live.
- Capture only the application, with no terminals, address bar, local file chooser, or secrets.
  Pause while selecting the sample file if the chooser would reveal personal paths.
- Use the current [screenshots](docs/assets/screenshots/README.md) as framing references.
- Leave the default **Deterministic evidence fallback · no LLM** label visible. Do not claim
  that a paid LLM was called. Do not switch to replay during the main walkthrough.

## 0:00–0:25 — The problem

“A payment can look ordinary on its own and still be part of coordinated abuse.
RiskWeave connects activity across accounts and shared infrastructure, then gives
an analyst the evidence to investigate. It surfaces candidates for review—not fraud verdicts.”

Show Investigations. Create **Shared infrastructure review**.

## 0:25–1:00 — From dataset to a review queue

“I upload a validated payment ecosystem and start analysis. The run and its results
are saved, so the case can be reopened and checked later.”

Upload the sample and start analysis. Show queued/running, then Completed. If waiting is
edited out, label the cut “Analysis completed” or explicitly open the previously completed run.

“These are ranked candidate rings. The score is not a calibrated fraud probability.”

Point out candidate count, observed sharing, and estimated exposure. Do not promise a
particular number of findings for arbitrary uploads.

## 1:00–1:40 — Ring Explorer and evidence

Open a candidate with visible sharing, such as **31A245** in the documented sample.

“Here we can inspect the customers and the infrastructure connecting them. Each displayed
link comes from computed evidence. Shared infrastructure can also be legitimate.”

Select a device or relationship; open its source evidence. Switch to Timeline and inspect
an event's original UTC timestamp, amount, and connected entities.

“The timeline gives context. Exposure is associated value, not confirmed loss; a refund
replaces the original purchase value rather than being added twice.”

## 1:40–2:20 — Grounded investigator

Open Investigator and ask **Which entities connect these customers?** Follow a citation.

“The investigator turns computed facts into a concise, cited summary. This recording uses
the deterministic mode, with no external model call. The optional LLM can select and order
facts, but it cannot invent evidence or change the detector's decision.”

“I can check a statement against its source instead of trusting a plausible explanation.”

## 2:20–2:50 — Validation and honest limits

Show the README's measured validation table or the frozen Phase 3 report briefly.

“Across five held-out synthetic ecosystems, network-aware PR-AUC was 0.971, compared
with 0.199 for the transaction-only model and 0.321 for the graph heuristic. We audited
synthetic shortcuts, published the before-and-after result, and kept weaker results visible.
These numbers do not establish real-payment performance.”

## 2:50–3:10 — Close

Return to the saved investigation.

“RiskWeave brings detection, relationship evidence, timelines, and grounded explanation
into one reviewable workflow. The next step is real-data validation—not automatic blocking.”

End on the product. Add the final recording URL to the README's **Demo video** section.
No recording or hosted-demo link exists yet.
