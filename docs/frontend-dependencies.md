# Frontend dependency maintenance

The application imports local shadcn component sources and @shadcn/react 0.3.0.
It does not execute the shadcn CLI. Previously, importing shadcn/tailwind.css
installed the whole CLI and its unrelated command-line dependencies into builds.

frontend/styles/shadcn-base.css preserves the complete shadcn 4.18.0 stylesheet
body, including variants, keyframes, scroll utilities and reduced-motion rules.
The original 16,041-byte body has SHA-256
bc7d83425702955b4cb67cb14ede9d603f9d912376d57a2d81d661094d2a782a.
The added header records provenance and the full MIT notice; the notice is also
distributed at public/licenses/shadcn-MIT.txt because CSS minification can remove
comments. Both standard hosting and the standalone Docker image ship public/.
Do not format or regenerate the vendored body without reviewing upstream changes.

Removing the unused CLI removed 286 installed packages and ten advisory findings.
The remaining moderate fast-uri finding was shared with webpack through
react-server-dom-webpack; a compatible lockfile patch updates 3.1.7 to 3.1.8.
No application framework downgrade or force update was applied.

The 5 October 2026 registry audit reports zero advisories across the complete
dependency graph, including development dependencies. The three generated CSS
bundles have identical byte lengths and identical SHA-256 hashes after removing
comments, before and after dependency removal. Existing production browser checks
verify the investigation flows and responsive/keyboard behavior; exact source
results are recorded in CLAUDE_HANDOFF.md and
results/operations/frontend-dependency-audit-20261005.json.

CI runs npm audit --audit-level=moderate after npm ci. The container smoke
also downloads the deployed MIT notice and compares it byte for byte with source. A newly reported advisory
or an unavailable advisory service fails this gate; investigate its actual
dependency path and compatible fixes rather than suppressing it or running a
force downgrade. A clean registry audit is not a comprehensive security review.

When adding components, use a separately reviewed, pinned CLI invocation as a
development operation. Inspect its source/config/CSS changes before committing;
do not restore the CLI as an application dependency merely to add components.
Retain @shadcn/react while message-scroller uses its runtime exports.

Upstream provenance: [shadcn/ui](https://github.com/shadcn-ui/ui),
[MIT license](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md).
