# Local Windows worker capacity baseline

Measured 5 October 2026 against application source
`3c1f62a27f979a37c86bde27c29190f98c8316ae` (application code identical to the
verified d5b9e18 source). Three generated seed-105 controls were stripped of labels
and processed in separate real worker processes with the unchanged pinned model.
A new isolated SQLite database and local object directory were used, not user cases.
Every worker completed persisted analysis; result checksums were read and verified.
The 1,000-payment control retained the historical stable result checksum.
A corrected rerun verifies that saved run model/build provenance matches the
worker configuration; all input/result hashes reproduced the first run. The table
records this rerun only. Times vary and are not a latency distribution.

| Requested payments | Actual events | Input MB | Result kB | Worker main s | Process/verification s | Peak working set MB | Peak commit MB |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 1,021 | 1.01 | 45.5 | 0.45 | 9.44 | 201.4 | 169.6 |
| 5,000 | 5,104 | 5.05 | 229.8 | 1.46 | 10.31 | 248.3 | 216.2 |
| 10,000 | 10,207 | 8.23 | 141.7 | 2.82 | 11.37 | 277.7 | 246.0 |

All sizes use decimal bytes. Worker main timing begins after its Python modules
are imported and includes input reading, parsing, inference/evidence generation,
serialization and persistence. The outer wall time includes process/bootstrap
and parent verification of saved result bytes. Memory counters cover the child
process lifetime, including imports; the helper observes the peak after completion.
API coordinator, browser, database service and other processes are excluded.
Windows peak working set is resident process memory; peak commit is a different
counter, not an interchangeable measurement or a whole-system memory budget.
See [Microsoft process counters](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters)
and [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo).

The generated controls have one seed/distribution and varying infrastructure/ring
shape; result size is not monotonic in payment count. One sample per size supplies
neither percentiles nor worst-case bounds. OS caches and other local processes
can affect times. This is not a Vercel, PostgreSQL or managed Workflow measurement,
not a release input limit and not real-data performance evidence. The public result
contains aggregates/hashes only and explicitly sets `production_ready: false`.

## Reproduce locally

On Windows, use a trusted operator-owned model with the verified SHA and a new
ignored fixture directory. No existing directory or case is overwritten.

```powershell
.venv/Scripts/python scripts/measure_windows_worker.py `
  --directory work/capacity-new-control `
  --model work/models/network-hgb.joblib `
  --model-sha256 182c06741a7fae5c389e79c8ea7c2888027528ab92ddde4479588805e0187c74
```

The script generates only synthetic data, fixes model provenance and one OpenMP
thread, uses fresh worker processes and a 300-second worker watchdog. It does not
submit to an existing database, call paid APIs, accept observed datasets or choose
a production threshold. Source/model/environment and measurements are recorded in
[the aggregate report](../results/capacity/windows-worker-20261005.json). Preserve
failed local fixture directories for diagnosis; no actual cases are deleted.

## Remaining capacity evidence

Repeat on the deployed runtime with its exact memory/duration/quota configuration,
PostgreSQL/TLS and managed Workflow. Include API-parent overhead, concurrent users,
cold/warm starts, dense/shared infrastructure, large candidate evidence, maximal
accepted input/result sizes, interruption recovery and all response paths. Record
multiple repetitions, latency percentiles and failures. Inspect actual function
bundle size and provider billing/allowances. Pick supported admission limits only
after those measurements; local data does not approve the current 100 MB budget.
