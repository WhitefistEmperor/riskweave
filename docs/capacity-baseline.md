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


## Shared-device density control

Application89ef246 was measured with all generated events assigned the earliest
observed device, using unchanged validated identities/timestamps/amounts and the
trusted model. Labels are stripped as before; this deliberately changed sharing
pattern is a capacity control, not a model accuracy benchmark. Three fresh workers
used a separate ignored fixture. Available host memory was about2.3 GB, so the
control used250/500/1000 payments; no larger safe capacity is implied.

| Actual events | Distinct customers | Worker main s | Peak working set MB | Result kB | Candidate evidence kB |
|---:|---:|---:|---:|---:|---:|
| 257 | 163 | 2.27 | 198.3 | 199.1 | 182.5 |
| 512 | 307 | 14.98 | 208.5 | 442.4 | 406.4 |
| 1,021 | 595 | 102.03 | 245.2 | 854.3 | 784.5 |

Each produced one connected candidate. The prior sparse1021-event worker took
0.65s on an earlier source; this comparison is directional, not an isolated
source-overhead experiment. Three read-only repetitions per saved run used only
26/27/27 bytes for bounded queue scalar reads (medians11.21/10.26/10.99ms).
Full selected sections retain source-fragment verification amplification.
See windows-worker-shared-device-before-20261005.json and
indexed-reads-shared-device-before-20261005.json in results/capacity/.

The feature source repeatedly traversed connected components and counted each
customer ego graph's edges. The continuation now tracks exact insert-only
component sizes with path compression and uses density1 only when an already
observed infrastructure group contains the complete ego network. Other shapes
still use the original NetworkX density calculation. No feature meaning, causal
observation order, threshold, trained artifact or stored result is intentionally
changed. Independent graph-oracle checks cover every event in generated,
single-device and overlapping-resource controls; a dense test forbids the costly
traversals. Exact full feature-vector hashes match before/after on three controls.
The512-event extraction changed from15.38s to0.39s in one local sample.
See results/capacity/exact-feature-equivalence-20261005.json. Complete optimized workers on343379c reproduce all original input/result hashes:

| Actual dense events | Before main s | After main s | After peak MB |
|---:|---:|---:|---:|
| 257 | 2.268 | 0.410 | 197.5 |
| 512 | 14.982 | 0.899 | 207.9 |
| 1,021 | 102.031 | 2.443 | 244.4 |

Sparse1021/5104/10207-event controls also retain original input/result hashes,
with main0.383/1.547/2.714s and peaks202.9/249.7/278.9MB. These are single local
worker samples. Reports are windows-worker-shared-device-optimized-20261005.json,
windows-worker-sparse-optimized-20261005.json and
indexed-reads-shared-device-optimized-20261005.json in results/capacity/. Both
source CI runs37286112105/37286116756 passed all six checks with301 Python and78
browser tests. No hosted capacity or observed model accuracy approval is implied.

Reproduce the density fixture only in a new private directory:

```powershell
uv run --no-sync python scripts/measure_windows_worker.py --directory work/new-shared-device-control --model work/models/network-hgb.joblib --model-sha256 182c06741a7fae5c389e79c8ea7c2888027528ab92ddde4479588805e0187c74 --shared-device --payments 250 500 1000
uv run --no-sync python scripts/measure_indexed_reads.py --directory work/new-shared-device-control
uv run --no-sync python scripts/measure_feature_vectors.py --output work/new-feature-capture.json --compare results/capacity/exact-feature-equivalence-20261005.json
```

Drivers refuse to overwrite existing fixture/output paths. Reports pin driver,
feature source, model and/or application identity and contain aggregate synthetic
proof only. Default worker sizes remain1000/5000/10000 when --payments is omitted.
This optimization retains the projected pairwise edge graph, which can still grow
quadratically. Mixed dense neighborhoods may still need expensive exact density
work. Browser graph layout/heap, maximal accepted input, concurrency, PostgreSQL
and managed provider limits remain open; do not approve admission budgets from
these small local controls.


## Browser graph density continuation

The same isolated real API/SQLite/object fixtures were opened in Chromium against
the production frontend through a Playwright HTTP relay injecting the fixed
synthetic development owner. Timings include relay overhead. This is not hosted
authentication/CORS/gateway proof. Before the frontend fix,513/1106 entities with
323/711 links took5.069/21.372s to display and Fit; their largest main-thread tasks
were4237/20190ms. The1021-event case timed out waiting60000ms for the canvas;
its final graph time/heap was not measured. See dense-browser-before-20261005.json.

The first corrected applicationa974aa6 used circular layout above250 nodes or500 links.
No entities, explicit links, original evidence or result hashes are removed.
Smaller networks retain the existing force layout. Entity/link selectors and
Focus selected remain available; a1201-node/1200-link browser check verifies all
selector entries, last-member inspection, its link and switching back to evidence.
First fixed measurements display+Fit513/1106/2121 entities in0.827/1.127/1.670s.
The corresponding largest tasks261/447/825ms still warrant further browser work.
These are single local samples, not capacity approval or percentiles.

To reproduce, serve only the complete shared-device fixture database/objects in a
separate loopback API with test development authentication and jobs disabled,
plus a production frontend. The driver requires exactly three completed fixture
runs owned by synthetic-capacity-only and matching report/result checksums. It
opens SQLite readonly and does not write API cases/reviews or saved objects.
Output must be a new path; only aggregates/hashes are published. Frontend graph
source and driver bytes are hashed. Do not point it at original user cases.

```powershell
node scripts/measure_dense_browser.mjs work/new-shared-device-control work/new-dense-browser-report.json http://127.0.0.1:8001 http://127.0.0.1:5173
```

Mixed graph shapes, browser response amplification/heap at accepted maxima,
concurrency, actual PostgreSQL/provider behavior and hosted capacity remain open.


Visual inspection of applicationa974aa6 after its79 local browser checks found
the previous0.15 minimum zoom still cropped the large circle even after Fit. The
correction lowers only large-network minimum zoom to0.0001, preserving the small
network behavior. Earlier Fit timings measure action completion rather than a
verified fully visible graph. Final visual/focused/source checks remain pending.


Final visual follow-up:lowering minimum zoom fit all2121 circular nodes, but the
large circle was too faint to inspect. Current correction uses deterministic grid
layout for large networks, excluding labels from node layout dimensions, with a
lower minimum zoom and tiny graph labels hidden below8 rendered pixels. Full IDs
remain accessible through entity selectors/inspector. The private final-grid
inspection showed all2121 nodes within the viewport and visible entity marks.
All7 focused large/responsive checks passed on the first grid revision; final
label-visibility build/source proof and pinned grid timing are pending.
