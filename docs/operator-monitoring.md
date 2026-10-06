# Operator monitoring

Run the private read-only snapshot with the backend environment configured:

```text
uv run --locked python -m ringsentinel.platform.operations
```

JSON output contains aggregate run counts, stored deadlines exceeded, failures
completed within the last 24 hours, and queued dispatch intents whose next check
is over five minutes late. It also counts queued jobs older than the queue wait
threshold and pending storage deletions older than the cleanup wait threshold,
with their oldest ages in whole seconds. Empty queues return `null` ages; future
timestamps clamp to zero. It contains no owner IDs, case names, run IDs, evidence,
tokens, provider handles or connection strings. PostgreSQL uses a read-only
transaction; a dedicated SELECT-only role is recommended. The tool checks schema
revision and refuses missing SQLite files rather than creating a database. It
never migrates, claims, retries, erases or changes saved work.

Exit codes are 0 for no detected condition, 1 for attention and 2 for unavailable
configuration/database/schema. Unavailability output is sanitized. An `ok`
snapshot is not proof of live authentication, model correctness, backup health
or complete hosted readiness. Rows without legacy deadlines cannot be assessed
as overdue execution; queued creation time still detects a long wait to start.
Counts describe the observation time, not a continuous trace or a measured SLA.

Queue and cleanup wait thresholds independently default to 30 minutes. Set values
from 1 through 1440 whole minutes in the private operator command:

```text
uv run --locked python -m ringsentinel.platform.operations --queue-wait-minutes 15 --cleanup-wait-minutes 60
```

Wait alerts mean strictly older than the threshold. Queue age starts at run
creation and applies only while queued, including accepted deliveries and legacy
runs with no execution deadline. An intentional backlog can still trigger it;
choose thresholds for the deployed workload and review capacity/budget constraints.
`queued_wait_exceeded` and `storage_cleanup_overdue` are alert counts, while
`pending_storage_deletions` counts all outstanding deletions regardless of age.
Changing thresholds does not change deadlines, claims, cleanup attempts or retention.

Connect the exit code/JSON to the deployment's authorized external monitor.
Poll HTTPS `/api/v1/ready` separately. Do not put database passwords in arguments
or public dashboards. Alert destinations/schedules are not configured by this
tool and have not been deployed.

For `EXECUTION_DEADLINE_EXCEEDED`, verify worker health and the configured bounded
recovery path; do not start an extra scheduler or manually clear execution claims.
For `DELIVERY_RECONCILIATION_OVERDUE`, check managed Workflow access, the daily
cron secret and reconciler registration, budgets and safe operator logs. For
`RECENT_ANALYSIS_FAILURE`, review failure codes through the authorized case/API
workflow and determine whether data, model provenance, capacity or service access
requires action. A historical failure stays visible for 24 hours; deduplicate
notifications in the external monitor. The report does not automatically retry
analysis or email anyone.

For `QUEUE_WAIT_EXCEEDED`, verify worker availability, delivery/reconciliation,
monthly dispatch budget and pending capacity. An accepted workflow is not proof
that its job has started; use the supported retry/deadline recovery path.
For `STORAGE_CLEANUP_OVERDUE`, inspect private storage availability and referenced
object conflicts, then run authorized bounded cleanup as documented in
[data lifecycle](data-lifecycle.md). Do not delete referenced objects or clear
cleanup rows by hand. A fresh pending deletion is counted before the alert threshold;
it does not imply completed physical erasure.

Local regression controls use actual queue/start/finish and failed object deletion,
then real cleanup. They verify privacy, boundary/override behavior and no mutations
from observation. A separate PostgreSQL17 control checks a real request-mode job
with a future deadline and a generated pending-deletion row, verifying both wait
alerts without changing either record. Consult the exact-source CI result before
claiming that database control passed. No monitor schedule or alert destination is
installed by these tests.

Set real response targets, alert ownership, backup RPO/RTO and escalation paths
before release. Verify interruption/recovery, encrypted snapshot scheduling,
hosted restore and monitoring against the exact deployed source commit.
