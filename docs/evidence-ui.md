# Evidence and replay interface

The frontend uses the existing detector, graph/event records, and `RingEvidenceService`.
`GET /api/snapshot?event_count=N&candidate_id=...` constructs candidates and evidence
from exactly the first N chronologically ordered events. Model scores are precomputed
from the existing causal feature extractor; the trained seed-105 held-out model is frozen.
The optional count includes history before the compact demonstration window.

Without `event_count`, the endpoint returns a completed-ecosystem snapshot, explicitly
labeled as such in the UI. Candidate IDs depend on membership and can change as a
component grows or merges. They are snapshot IDs, not persistent case identifiers.

Opening the live candidate watch preserves the current event count and candidate ID.
The Ring Explorer sidebar opens the completed ecosystem for retrospective review.
Both views expose only computed candidate nodes, edges, members, event timeline,
sharing queries, refunds, temporal buckets, merchant links, exposure, and behavior.

The first suspicious timestamp is the first above-threshold event in the candidate.
The first connected precursor timestamp is the earliest qualifying component in its
event lineage (two linked events from at least two customers). This is not a claim
that the final membership existed at that time. The timeline intentionally omits a
final risk score from this earlier milestone. Attack stages are separately labeled
demo ground truth and are bounded by the snapshot timestamp.

Shared-infrastructure highlighting means sharing was observed; it is not proof of
fraud, a causal feature attribution, or a model explanation. The detector score is
uncalibrated. Temporal buckets report observed counts, not inferred synchronization.
