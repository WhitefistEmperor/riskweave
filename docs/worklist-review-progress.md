# Worklist review progress

The paged worklist summarizes each visible case's latest completed analysis.
New run completions save their unique candidate total in migration 0008, alongside
result persistence. Worklist reads use projected database columns and aggregated
current review dispositions, without reading result files or notes. Only cases
on the owner-scoped page are queried. Empty pages have no summary queries.

Assessed means the current disposition is Investigating, Escalated or Dismissed.
Returning a candidate to Unreviewed removes it from assessed counts. This is not
completion of an investigation, confirmed fraud or a training label. The displayed
breakdown and link identify the latest completed run; a newer queued/running/failed
run does not inherit or erase earlier completed assessments. A newly completed run
starts with its own reviews. Summaries refresh with the worklist response.

Older runs have a null candidate total; the UI explicitly displays total unknown.
No result file is parsed on demand to guess it, and no missing total becomes zero.
A new genuine empty result has a known zero total. Cases with no completed run show
No completed analysis. Older API responses without summary support show unavailable.
Counts that contradict known totals fail closed; the browser also validates count
arithmetic and exact correspondence to visible case IDs before rendering.

Apply migration 0008 explicitly with all writers stopped, then restart the API.
Existing results, checksums and reviews remain untouched. Normal database backups
include the new nullable count; PostgreSQL 17 restore tests verify the summary after
restore in both storage modes. Live hosted worklist capacity remains unverified.
