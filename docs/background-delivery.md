# Saved-run background delivery

This optional adapter uses the pinned Python `vercel-workflow==0.11.0` SDK.
It has been exercised with the real local SDK queue, including actual isolated
model inference. Managed Vercel execution, deployment interruption and quota
behavior still require hosted verification. The Python SDK is currently beta.
The default local scheduler and browser-dispatched request mode remain available.

## Configuration

First configure [database storage and bounded request execution](request-execution.md).
Then set `RINGSENTINEL_BACKGROUND_DISPATCH=vercel_workflow`, enabled jobs and an
analysis timeout no greater than 240 seconds. Apply migration `0006` explicitly;
it adds delivery intent, monthly start accounting and reconciler admission without
rebuilding case/review tables. Readiness checks the new tables in this mode.

Production requires the managed Vercel runtime (`VERCEL_DEPLOYMENT_ID` and the
managed workflow world), the existing PostgreSQL/JWT/model/storage safeguards,
and `RINGSENTINEL_DISPATCH_CRON_SECRET` of at least 32 characters. An embedded
local queue is rejected in production. A disposable local SDK world does not
provide cloud crash durability.

For isolated HTTP/container verification, `compose.background.yml` uses
`scripts/serve_background_test.py`. SDK 0.11's embedded queue requires a task-owned
AnyIO scope; initializing it inside an ordinary FastAPI request breaks that scope.
The test harness primes and closes the local SDK in its root task before serving
HTTP. It refuses production and managed Vercel environments. Its private cleanup
import is confined to test tooling. Do not enable local SDK mode on the normal
Uvicorn entry point or deploy this test harness publicly.

The registry is `ringsentinel.platform.workflows:wf`, declared in
`[[tool.vercel.workflows]]` in `pyproject.toml`. A deployable API entry point,
SDK-generated queue routes, their access controls, the actual supported Python
runtime and bundled model still need verification in the Vercel build.
Do not expose a custom unauthenticated workflow-start endpoint.

Set a backend-project daily cron for `GET /api/v1/operations/reconcile-delivery`,
for example `0 0 * * *`. Register it in that project's eventual `vercel.json`;
no deployed cron currently exists. Set Vercel `CRON_SECRET` to the same secret
as `RINGSENTINEL_DISPATCH_CRON_SECRET` so its bearer header authorizes the route.
Analyst identity headers cannot authorize maintenance. Keep cron secrets out of
public frontend variables. The route also performs a bounded immediate repair pass.

## Delivery and execution

Run creation, monthly admission and an opaque delivery ticket commit in one SQL
transaction. The HTTP start route tries queue submission before returning. It
reports `dispatch_state=pending` when submission is interrupted and `accepted`
after provider acknowledgment. These describe delivery, not an inference outcome.
The console polls saved status without posting `/execute` for managed workflows.
Older clients calling that endpoint only retry delivery of the same saved run.

Database leases serialize submission across instances. A lease lasts 30 seconds;
provider acknowledgment is bounded at 10 seconds. Failed submission backs off
for 60 then 120 seconds. At most three starts are attempted per saved run,
including interrupted or ambiguous submissions. A stale acknowledgment cannot
overwrite a newer lease. A provider may accept a submission before its acknowledgment
is lost; duplicate workflows therefore share the same application run/ticket and
the existing distributed execution claim prevents repeated inference.

The workflow resolves the committed owner from the database, then executes the
existing request worker. Queue arguments contain only opaque run/ticket IDs;
dataset bytes, analyst tokens and internal exception text are not serialized into
workflow arguments or returns. A changed model digest fails a queued run rather
than silently substituting another model version. Completed results remain immutable.

Busy capacity sleeps for 120 seconds, with at most 40 attempts before a safe
`CAPACITY_TIMEOUT`. Analysis is still bounded by the subprocess watchdog and
database deadline. Running work is not re-enqueued after an interrupted worker;
it fails safely and an analyst must explicitly start a new run. Terminal provider
workflows are retried only while the application run is still queued. Accepted
workflow checks defer their next inspection to prevent starving pending deliveries.

One reconciler is admitted per UTC day, with at most two submission attempts.
It makes 27 bounded hourly passes to overlap the daily Hobby cron's scheduling
window. Admission leases and saved-run claims remain authoritative if reconcilers
overlap. A failed controller may leave recovery delayed until the next daily cron
or another authorized maintenance pass; this is not an immediate-delivery SLA.

## Free-tier bounds and erasure

`RINGSENTINEL_DISPATCH_STARTS_PER_MONTH` defaults to 50 analysis workflow starts,
including submission retries. `max_pending_runs` defaults to 10 in managed mode
when not explicitly configured; set `RINGSENTINEL_MAX_PENDING_RUNS=10` when using
the example environment, which otherwise specifies the local-mode value of 100.
The fixed workflow loops and reconciler admission bound application-generated
events. They do not reserve Vercel allowance or cap account-wide billing, function
usage, queues, transfer or database costs. Verify the owning account's free quotas;
do not enable paid resources or upgrade plans under this project's instruction.

Case erasure removes its SQL dispatch intent with inputs, results and review data.
A late workflow then returns `deleted` and cannot recreate the case. Anonymous
monthly/daily admission totals remain. Provider workflow history still contains
opaque identifiers until its own retention expires, and queued provider activity
may continue until it observes deletion. Hosted retention, cancellation and
cross-provider/snapshot erasure procedures remain release work.

References: [Python Workflow SDK](https://workflow-sdk.dev/docs/getting-started/python),
[Workflow pricing and retention](https://vercel.com/docs/workflows/pricing),
[Hobby cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing).
