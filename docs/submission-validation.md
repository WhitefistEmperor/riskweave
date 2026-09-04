# Submission verification — Phase 6

Date: **2026-09-04**. Starting checkpoint: `88501999328717c8da64e3f788a7d207e74d4dd1`.
Branch: `phase5b-frontend-v2`. Local runtime: Windows, Python 3.14.6, Node.js 24.19.0.

This pass changes only submission documentation, curated screenshots, and ignore rules.
No deployment, detector/scoring/threshold/graph/evidence/benchmark/generator/replay changes,
or production-architecture changes were made. Historical reports and benchmark artifacts
remain intact. The architecture document describes existing behavior; it does not implement
a different architecture.

## Checks rerun in this pass

| Check | Actual result |
|---|---|
| `uv run --locked --extra dev pytest -q` | **94 passed**, 2 dependency warnings, **110.69 seconds** |
| `uv run --locked --extra dev ruff check .` | Passed |
| `npm test` in `frontend` | **27 passed**, **2.1 minutes**; 22 browser/E2E + 5 non-browser checks |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run build` with explicit production environment/proxy | Passed; all five build stages completed |
| Migration quick start | Fresh SQLite upgrade and repeated upgrade both passed |
| Documented sample command | Validated **2,824 entities / 1,021 events**, seed 105 / 1,000 payments |
| Screenshot walkthrough | Real create/upload/analysis/evidence/timeline/investigator/list; **6 captures**, **0 page errors**, no response mocks |
| Benchmark SHA-256 | Matches the preserved Phase 3 artifact |
| Repository review | Source/application/lockfiles/results unchanged; curated assets only; no tracked runtime data or high-confidence secret-pattern hits |
| Documentation links | Relative file/image links and heading anchors checked; no missing targets in the final documentation |

The full frontend tests ran against the existing local API and production-preview frontend
with the deterministic investigator. The production build was then rerun with
`RINGSENTINEL_ENVIRONMENT=production` and
`RINGSENTINEL_API_PROXY_TARGET=http://127.0.0.1:8000` in the frontend process.
These settings do not establish real production authentication or deployment readiness.

The Python warnings concern Starlette's httpx TestClient and an anyio BlockingPortal alias.
Build notices remain for JSON import attributes, forwarding credentials to the configured
proxy origin, plugin timing, and Vinext's unknown route classification. They were not hidden
or “fixed” through unrelated application changes. All relevant commands exited successfully.

The screenshot-only scratch automation initially used an empty-worklist heading incorrectly,
then checked a still-loading list before reuse. Those capture-script assumptions were corrected;
the final gallery came from one fresh development identity and a real saved investigation.
The application and existing tests were not changed. Earlier local scratch cases remain untouched
and are not included in the gallery or repository.

## Preserved benchmark

File: [`results/phase3/phase3_results.json`](../results/phase3/phase3_results.json)

```text
42c0234331f2b467ccc296f6579478d2feaf7c71e9c159387b6674a09b27e976
```

PowerShell reproduction:

```powershell
Get-FileHash results/phase3/phase3_results.json -Algorithm SHA256
```

Bash reproduction: `sha256sum results/phase3/phase3_results.json`.

README metrics are transcribed from the preserved [Phase 3 report](../results/phase3/phase3_summary.md).
Experiments were not rerun or selectively regenerated. The before/after synthetic shortcut fix,
weaker held-out archetype, exposure errors, and uncalibrated-score limits remain visible.
This does not establish performance on real payments.

## Dependency audit provenance — not a new audit

The latest existing audit was **Phase 5C, 2026-09-04**:

- `npm audit`: **0 affected packages**, full reported 702-dependency tree.
- `pip-audit`: **no known third-party vulnerabilities**; unpublished local package skipped.

Dependency manifests and lockfiles are unchanged. These are dated prior results, not a new
registry lookup or guarantee against subsequently published advisories. The audit methods,
earlier findings, and limitations remain in [dependency audit history](dependency-audit.md)
and [Phase 5C final verification](phase5c-final.md).

## Submission integrity and remaining manual steps

- Existing MIT license and attribution retained; no team identity or ownership invented.
- Ignore rules also cover SQLite sidecars, logs, and desktop metadata. `.env.example` remains
  the intentional tracked template. Generated inputs/results, local databases, caches,
  node_modules, and build/test output remain ignored; no useful history was removed.
- Six screenshots were individually inspected for clean states, real evidence, and absence
  of secrets, filesystem paths, consoles, or junk test data. They are not accuracy evidence.
- The README contains a GitHub Mermaid architecture diagram. GitHub-hosted rendering and
  remote CI were not run; no remote is configured in this checkout.
- The recording is intentionally not created. Add its real URL to the README and apply
  the suggested [GitHub metadata](submission-metadata.md) before submission.
- No staging/deployment work occurred. Real OIDC gateway/TLS, Docker/Linux, and live PostgreSQL
  gates remain outstanding as described in the [Phase 5C report](phase5c-final.md).

The Phase 6 commit hash and final clean-tree status are provided after the local checkpoint
is created; this report intentionally does not attempt to embed its own commit hash.
