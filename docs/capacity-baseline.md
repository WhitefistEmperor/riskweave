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

## Rerun after indexed reads and paged console

On source cc38ca45f7ea8aca753ffbe9e27c2139da19ca58 (application source 134c67c),
the same three controls ran in a new isolated fixture. Every historical input and
result checksum reproduced. This includes migrations 0009/0010 and new overview
scalar metadata; the prior table predates them. One fresh worker per size:

| Actual events | Worker main s | Process/verification s | Peak working set MB | Peak commit MB | Section index rows |
|---:|---:|---:|---:|---:|---:|
| 1,021 | 0.65 | 13.22 | 202.9 | 170.5 | 20 |
| 5,104 | 2.29 | 14.66 | 248.5 | 217.2 | 26 |
| 10,207 | 4.34 | 16.93 | 278.0 | 246.2 | 14 |

See [worker report](../results/capacity/windows-worker-indexed-20261005.json).
Timing differences from the earlier sample do not isolate index overhead: caches,
other processes and process startup also differ. These are still single sparse
controls, not a distribution or an approved deployment limit.

A read-only companion driver performs three sequential service calls per path
on each saved generated run, forbids whole-object reads, caps range reads at 2 MB
and reconstructs the largest candidate evidence with chunk/final SHA checks.
It measures SQLite/local-storage service calls, excluding HTTP encoding, browser,
API process memory and provider/network costs. Cache state is uncontrolled.

| Events | Overview bytes / median ms | First page bytes / median ms | Selected evidence bytes | Evidence storage bytes / median ms |
|---:|---:|---:|---:|---:|
| 1,021 | 93 / 55.19 | 6,146 / 27.21 | 8,105 | 91,032 / 20.95 |
| 5,104 | 94 / 38.03 | 16,041 / 29.27 | 26,887 | 459,698 / 29.14 |
| 10,207 | 95 / 34.58 | 12,059 / 13.77 | 47,354 | 283,338 / 24.96 |

The overview uses six tiny ranges. Pages request up to eight summaries. Evidence
manifest and delivery each verify the containing source fragment; every result
here fits one source fragment, so storage bytes are twice complete result bytes.
That is internal bounded range verification, despite whole-object reads being
forbidden; it is not a claim that evidence reads only selected bytes internally.
Dense results crossing multiple fragments need separate measurements. No evidence
cache or weaker checksum verification was introduced to reduce these numbers.

See [read report](../results/capacity/indexed-reads-20261005.json) for each repetition.
Reproduce after creating a fresh baseline fixture using the command above:

```powershell
.venv/Scripts/python scripts/measure_indexed_reads.py --directory work/capacity-new-control
```

The companion writes only a new report in the fixture directory, never migrates,
starts jobs or alters saved rows/objects. It requires the generated baseline marker,
uses the fixed synthetic owner and verifies source/result provenance. Reports
publish only aggregates and hashes. Large candidate summaries, selected-section
browser memory, PostgreSQL range costs and all hosted capacity gates remain open.
