# Operator monitoring

Run the private read-only snapshot with the backend environment configured:

```text
uv run --locked python -m ringsentinel.platform.operations
```

JSON output contains aggregate run counts, stored deadlines exceeded, failures
completed within the last 24 hours, and queued dispatch intents whose next check
is over five minutes late. It contains no owner IDs, case names, run IDs, evidence,
tokens, provider handles or connection strings. PostgreSQL uses a read-only
transaction; a dedicated SELECT-only role is recommended. The tool checks schema
revision and refuses missing SQLite files rather than creating a database. It
never migrates, claims, retries, erases or changes saved work.

Exit codes are 0 for no detected condition, 1 for attention and 2 for unavailable
configuration/database/schema. Unavailability output is sanitized. An `ok`
snapshot is not proof of live authentication, model correctness, backup health
or complete hosted readiness. Rows without legacy deadlines cannot be assessed
as overdue; counts describe the observation time, not a continuous trace.

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

Set real response targets, alert ownership, backup RPO/RTO and escalation paths
before release. Verify interruption/recovery, encrypted snapshot scheduling,
hosted restore and monitoring against the exact deployed source commit.
