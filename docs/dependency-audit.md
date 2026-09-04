# Dependency review

## Phase 5C fresh audit — 2026-09-04

Both required fresh scans completed successfully on the Phase 5C dependency state:

- `npm audit --json --fetch-timeout=30000 --fetch-retries=0 --registry=https://registry.npmjs.org`:
  **0 affected packages**, all severity categories zero; reported tree 702 dependencies
  (prod 469, dev 146, optional 157, peer 35; categories overlap). Full tree, not omit-dev.
- `uv run --with pip-audit pip-audit --format json`: **no known vulnerabilities** in audited
  third-party packages. Includes the audit-tool overlay; unpublished local RingSentinel skipped.
- New narrowly scoped auth dependency: PyJWT 2.13.0 with cryptography 50.0.1, cffi 2.1.1 and
  pycparser 3.0. Existing locked packages were not upgraded. Frontend lockfile unchanged.
- Initial sandbox npm query failed; official-registry retry with authorized network access passed.
  This supersedes the unavailable post-update scan recorded in the historical Phase 5A section.

No unresolved advisory findings were returned by these scans. Remaining operational risks are
separate: Vinext beta runtime maturity, inline hydration without nonce-based script CSP, retained
development tooling in the frontend image, unpinned container base-image digests and no actual
Linux image/SBOM scan. No container runtime exists here; a package scan is not an image scan or a
security certification. Do not auto-upgrade frameworks or chase counts with breaking changes.

## Historical Phase 5A review

Measured on 2026-09-04. An advisory scan is not a penetration test, and a clean
scan is not proof of security. Findings below count affected packages as reported
by npm, not distinct vulnerabilities. No dependency was upgraded automatically
with `npm audit fix`.

## Commands and baseline results

```text
uv run --with pip-audit pip-audit --format json
npm audit --json --fetch-timeout=30000 --fetch-retries=0 --registry=https://registry.npmjs.org
```

The Python scan completed successfully with **no known vulnerabilities** in the
installed third-party environment. The isolated pip-audit overlay also includes
the audit tool's dependencies. The local `ringsentinel` package is not published
on PyPI and was explicitly not audited. The project's `pyproject.toml` and
`uv.lock` were not modified by this check.

The frontend baseline returned **11 affected packages: 8 high, 2 moderate,
1 low, 0 critical**. The first sandboxed query failed to reach npm. A default
timeout retry eventually timed out; the explicit 30-second, zero-retry command
above succeeded. A network failure was not counted as a passing audit.

## Classification and scoped updates

| Package/group at baseline | Classification and applicability | Target update |
| --- | --- | --- |
| `react-server-dom-webpack` 19.2.6 | Production-critical priority, high-severity RSC server-function resource exhaustion. The app uses an RSC-capable server, so it is not safe to dismiss this as browser-only. | Match React, React DOM and RSC at 19.2.8. |
| `vinext` beta.5 → `image-size` 2.0.2 | Production dependency, transitive high-severity image parser denial of service. RingSentinel does not accept analyst image uploads; exploitability of every image path was not tested. Not labeled a false positive. | Vinext 1.0.0-beta.9, plus compatible `@vitejs/plugin-rsc` 0.5.34. |
| Vite 8.0.13 | Development server: Windows alternate-path file exposure and UNC editor behavior. Not applicable to the Linux Vinext production server's non-development serving mode, but relevant to this Windows developer environment. | Vite 8.2.2, same major version. |
| `@cloudflare/vite-plugin` 1.37.1 / Wrangler 4.92.0 | Development/build-tool direct packages, with transitive advisories in Miniflare, Sharp, Undici, WebSocket and esbuild. No Cloudflare deployment is used in Phase 5A. | Plugin 1.54.4 with its matching Wrangler 4.129.0. |
| `miniflare`, `sharp`, `undici`, `ws`, `esbuild` | Transitive development/emulation tree. Individual conditions include malformed image/WS data, optional proxy/cache behavior, and Windows development serving. These vulnerable versions remain findings even if a particular application path is unused. | Resolve through the parent updates; do not impose arbitrary transitive overrides. |

The selected updates stay within the existing React 19.2, Vite 8, Vinext 1.0 beta,
and Cloudflare plugin 1.x lines; this is not a framework replacement. The updated
Cloudflare plugin itself depends on Miniflare 5 alpha, so its build compatibility
must be checked explicitly rather than inferred from a parent semver number.
The frontend container intentionally retains the tested Vinext dependency closure
(including tool peers), so unused development packages are still present on disk.
This is disclosed rather than hidden by an `--omit=dev` scan.

Primary advisory details: [React RSC DoS and patched versions](https://github.com/react/react/security/advisories/GHSA-wx67-qw84-cm4g),
[Vite Windows path restriction bypass](https://github.com/vitejs/vite/security/advisories/GHSA-fx2h-pf6j-xcff).
Other advisory IDs recorded by npm include GHSA-w3rx-r6r6-pgpr and
GHSA-5p2g-fcmc-qvqq (`image-size`), GHSA-f88m-g3jw-g9cj (`sharp`),
GHSA-96hv-2xvq-fx4p (`ws`), and GHSA-g7r4-m6w7-qqqr (`esbuild`).

## Post-update verification

The installed manifest now contains React/React DOM/RSC 19.2.8, Vinext beta.9,
Vite 8.2.2, `@vitejs/plugin-rsc` 0.5.34, Cloudflare plugin 1.54.4 and Wrangler
4.129.0. The Cloudflare peer requirement also required matching
`@cloudflare/workers-types` 5.20260903.1; no forced peer resolution was used.

Read-only `npm ls image-size miniflare sharp undici ws esbuild --depth=4 --json`
completed successfully. It confirmed that `image-size` is no longer in the
dependency tree and the affected tree now resolves Miniflare 5.20260903.0-alpha,
Sharp 0.35.2, Undici 7.29.0, ws 8.21.0 and esbuild 0.28.1. This is version-level
verification, not a substitute for the fresh advisory scan or runtime tests.

The post-update full audit was attempted **three times** against the official
npm registry: twice with `--fetch-timeout=30000 --fetch-retries=0`, and once
with `--fetch-timeout=45000 --fetch-retries=0`. Every attempt exited 1 with a
network timeout at the bulk-advisory endpoint, without a vulnerabilities result.
Thus the post-update count is **unavailable, not zero**. The 11 baseline affected
packages have version-level remediation through the selected parent updates,
but the remaining advisory count must be confirmed when npm is reachable.
No audit findings were suppressed or marked false solely to obtain a clean count.

Production-build, lint, TypeScript and browser-regression outcomes are recorded
separately in `docs/phase5a-verification.md`; this audit does not imply that those
checks passed before they actually ran.

## Remaining security work

Compatibility verification after these updates: frontend lint, TypeScript and
production build passed; all 8 browser tests passed against the production build
(including the five original Phase 4 tests and the real persisted workflow).
This verifies application compatibility, not a replacement for the unavailable
post-update advisory count.

Dependency vulnerability data changes over time. Re-scan before any later staging
or public deployment, minimize and audit the actual Linux runtime image, pin
base images and CI actions by reviewed immutable digest, add an SBOM/image scan,
and verify relevant threat-model paths. These are Phase 5C deployment-hardening
tasks, not evidence that Phase 5A is a secure multi-user production deployment.
