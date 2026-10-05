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
authentication/CORS/gateway proof. Original513/1106-entity networks with323/711
links took5.069/21.372s to display and Fit, with4237/20190ms largest tasks.
The1021-event case timed out waiting60000ms for its canvas; its final graph
time/heap was not measured. See dense-browser-before-20261005.json. A first circle
revisiona974aa6 passed79 local browser checks but visual inspection found a
cropped/faint overview. Final grid proof supersedes those intermediate timings.

Applicationbdac888 uses deterministic grid layout above250 nodes or500 links,
excludes labels from layout dimensions and permits lower zoom so Fit can show
the complete grid. Tiny graph labels hide below8 rendered pixels. Full IDs remain
in selectors/inspector. Smaller networks retain their force layout/style; every
graph entity/link and saved evidence/result hash remains unchanged. Private visual
inspection confirms all2121 nodes fit the viewport with visible entity marks.
The1201-node/1200-link regression verifies every selector entry, last-member
selection, its explicit relationship, focus and returning to evidence.

| Events | Graph entities/links | Evidence ready s | Network+Fit s | Network JS heap MB | Largest task ms |
|---:|---:|---:|---:|---:|---:|
| 257 | 513 /323 | 1.484 | 1.222 | 19.8 | 287 |
| 512 | 1106 /711 | 1.059 | 1.236 | 25.8 | 467 |
| 1021 | 2121 /1471 | 1.131 | 2.916 | 53.8 | 1229 |

Network+Fit includes two animation frames. No browser/HTTP errors, selection and
return-to-evidence passed and no horizontal overflow. See
results/capacity/dense-browser-grid-20261005.json for actual source/driver/graph
hashes and all aggregates. These are single samples, not percentiles. The1229ms
task and53.8MB heap warrant further larger-case work. Final lint/typecheck/build,
7 focused browser checks and both exact-source CI runs37289226934/37289232195
passed (all six checks,301 Python/79 browser and actual PostgreSQL/SDK/restores).

To reproduce, serve only a complete shared-device fixture database/objects in a
separate loopback API with test development authentication and jobs disabled,
plus a production frontend built from the recorded source. The driver requires
exactly three completed runs owned by synthetic-capacity-only and matching saved
report/result checksums. SQLite opens readonly. No cases/reviews/saved objects are
written. Output must be a new path; only aggregate hashes/metrics are published.
Do not point this fixture-only driver at original user cases or hosted services.

```powershell
node scripts/measure_dense_browser.mjs work/new-shared-device-control work/new-dense-browser-report.json http://127.0.0.1:8001 http://127.0.0.1:5173
```

Mixed graph shapes, accepted maxima, response amplification/heap, concurrency,
actual PostgreSQL/provider behavior and hosted capacity remain open.


## Compact exact customer projection:source198d2db verified

The feature extractor replaces individual NetworkX projected edge dictionaries
with exact integer adjacency/repeated-sharing bitsets, retaining all edge existence
and at-least-two-resource information used by the frozen features. Causal resource
membership and component sizes remain exact. Induced density counts masked
neighbors and follows the original divide-then-multiply float order. It does not
sample, approximate or drop links. Worst-case memory is still quadratic in bits;
resource masks can add sparse overhead. Actual worker/memory samples are below; hosted gates remain.

Five full generated feature captures reproduce original input/feature hashes,
including valid mixed dense controls. Mixed512-event extraction8.106s to0.138s
in a single sample. See compact-feature-equivalence-20261005.json. Nine focused
tests cover causal graph-oracle shapes, late component bridging, label blindness,
prefix equivalence and absence of projected NetworkX allocation. Exact source CI37291647939/37291657451 passed all six checks with304 Python/79
browser tests. Local full Python302 passed/2 PostgreSQL-only skips and Ruff passed.
All nine complete input/result hashes match originals; see the worker proof below.

The first mixed worker fixture failed strict ingestion because per-event resource
changes broke refund context. The fixed control assigns groups per customer so
original-payment/refund references remain consistent. Feature capture now invokes
the same parse_input validation. Published windows-worker-mixed-before-20261005.json
contains only the valid104/257/512-event controls on sourcee6ce32e. Driver changes
were not yet in that source; the report captures their actual measurement hash.

```powershell
uv run --no-sync python scripts/measure_feature_vectors.py --mixed --output work/new-compact-capture.json --compare results/capacity/compact-feature-equivalence-20261005.json
uv run --no-sync python scripts/measure_windows_worker.py --directory work/new-mixed-control --model work/models/network-hgb.joblib --model-sha256 182c06741a7fae5c389e79c8ea7c2888027528ab92ddde4479588805e0187c74 --mixed-infrastructure --payments 100 250 500
```


All nine worker controls reproduce complete original input/result hashes and the
trusted model artifact. Report:compact-worker-equivalence-20261005.json. Mixed512
main7.859s to0.409s, peak206.1MB to197.3MB; dense1021 main2.443s to0.951s, peak
244.4MB to203.1MB. Sparse10207 main2.714s to2.809s and peak278.9MB to282.9MB;
resource bitsets incur small sparse overhead. Do not claim uniform reductions.

| New dense events | Customers | Main s | Peak working set MB | Result MB |
|---:|---:|---:|---:|---:|
| 2552 | 1426 | 3.429 | 221.1 | 1.540 |
| 5104 | 2850 | 11.727 | 252.8 | 1.905 |
| 10207 | 3120 | 25.332 | 282.6 | 1.852 |

All sources pin198d2db and unchanged trusted model SHA. Reports are
windows-worker-compact-shared-device-large-20261005.json and
indexed-reads-compact-shared-device-large-20261005.json. Indexed read measurements
forbid whole-object reads. These results STILL FIT ONE native2MiB source fragment;
selected manifest/delivery each verifies the containing fragment, so the largest
1851840-byte result causes3703680 total storage bytes over2 reads. The boundary
controls3063/3573/4083 events also stayed below2MiB. Native generated multi-fragment
capacity is unproved. Boundary timings overlapped one small real browser workflow;
all measurements are ambient single samples, not percentiles or hosted limits.

Larger real browser views display+Fit4108/5394/5168 entities with2542/3068/3069
links in4.288/4.934/4.322s. No browser/HTTP errors, selection and return-to-evidence
passed, no horizontal overflow. Largest tasks1673/2519/2413ms; network-stage
renderer JS heaps144.6/69.3/65.7MB. These are instantaneous samples without forced
GC, not per-case peak RAM/scaling forecasts. See dense-browser-compact-large-20261005.json.
The source snapshot198 has the same frontend tree as the servedbdac888 build;
exact graph/driver source bytes are captured. Correction: these overall longest
tasks include selector opening/selection and do not isolate graph setup. The
newest handoff records cancellable initialization and bounded searchable choices,
with separate graph and selector phase measurements. Accepted maxima, concurrency,
provider/private-PG costs, actual multi-fragment extremes and hosting remain open.

### Cancellable large networks and bounded choices (ae8e940)

Large graphs now load all elements in cancellable100-element animation-frame
batches with progress, followed by full Fit. Large entity/relationship selectors
render64 choices per page with full-identifier search; this never filters graph
data. Eight focused checks include navigation during8001-entity/8000-link loading
and inspection of the last entity/relationship. All80 frontend tests pass locally.

Pinned real API/local production-browser report:
`results/capacity/dense-browser-incremental-20261005.json`.

| Events | Entities / links | Display + Fit seconds | Graph maximum task ms | Selector maximum task ms | Overall maximum task ms |
|---|---|---|---|---|---|
|2552|4108 /2542|4.882|584|568|584|
|5104|5394 /3068|6.330|760|859|859|
|10207|5168 /3069|5.800|706|752|752|

Every sample preserves saved result hashes/counts, reports zero browser/HTTP
errors, working selection/return to evidence and no overflow. Intermediate
incremental code before bounded selectors had selector tasks1837/2102/2207ms;
phase instrumentation corrects the earlier claim that all overall delay came
from initialization. Residual600-860ms tasks still need accepted workload limits.
These ambient local synthetic samples establish neither percentiles/concurrency
nor hosted authentication or capacity. Instantaneous network renderer heaps
80.3/62.5/64.7MB are not peak process memory. Original data/model are unchanged.

### Generated native multi-fragment controls (b97cde2)

The worker driver now optionally appends128 characters consistently to generated
customer entity/event identifiers. Actual strict ingestion and the unchanged
worker generate results exceeding the2000000-byte native fragment boundary.
This varies input identifier width; saved output is not padded afterward.

| Events | Result bytes | Native fragments | Evidence bytes | Worker seconds | Peak working set MB |
|---|---|---|---|---|---|
|1021|1411961|1|1275521|0.876|206.8|
|2552|2570587|2|2309700|3.002|221.7|
|5104|3200467|2|2862549|9.808|254.1|

The read driver verifies full immutable result reconstruction from native
fragments, then each selected evidence section's complete hash and delivery chunk
hashes. Each path is measured three times, whole-object reads forbidden and every
individual storage read bounded to2000000 bytes. Largest evidence delivery median
0.102s reads7601401 total bytes over5 reads because source fragments are verified
again across manifest/delivery chunks. First queue page reads27 bytes over2 reads.
This is bounded read amplification, not selected-bytes-only storage behavior.

Actual local browser controls consume the verified evidence through isolated
API8002 and the unchanged production frontend. All three pass inspection/return
to evidence with zero browser/HTTP errors and no overflow. Graphs2121/4108/5394
entities retain1471/2542/3068 links; display+Fit2.593/4.672/6.066s, overall maximum
tasks369/586/817ms. Instantaneous network renderer heaps48.8/79.0/136.9MB are not
peak RAM. Local owner relay does not prove hosted authentication.

Reports: windows-worker-long-identifiers-20261005.json,
indexed-reads-native-fragments-20261005.json and
dense-browser-native-fragments-20261005.json. This closes the missing generated
two-fragment sample; higher fragment/candidate extremes, repeated worker
percentiles, actual PostgreSQL capacity and hosted admission remain open.
