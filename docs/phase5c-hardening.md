# Phase 5C production hardening

Baseline `b552cb7ac29bbed93ea4398e8ebe22919d9ac389`, branch `phase5b-frontend-v2`.
No public/staging deployment. Detector, generator, graph, evidence and benchmark are out of scope.

## Authentication and security milestone

Production supports `auth_mode=jwt`: offline RS256 verification with PyJWT/cryptography and an
operator-provisioned public JWKS file. Issuer, audience, required scope, expiration, not-before,
issued-at and subject are checked. Default maximum token lifetime is 900 seconds. Algorithms are
fixed; token key URLs are never fetched. Unknown keys fail closed. Rotation: provision overlapping
public keys, restart the single backend, wait out the old token lifetime, remove the old key/restart.
Identity is a deterministic hash of the verified issuer/subject pair, not a client ID or email.
Missing/invalid credentials return 401; valid credentials without the analyst scope return 403;
cross-owner objects retain non-disclosing 404. Development headers only work in development/test.
`disabled` denies all protected routes; missing/invalid JWT configuration prevents startup.

The minimal adapter is not an identity provider or a browser login implementation. Before staging,
configure a maintained OIDC gateway with an application-specific audience/scope and short-lived
access tokens. The gateway authenticates every UI/API request and forwards the user's access token
to `/api` as Authorization. Prefer routing `/api` directly to the private backend. Strip incoming
identity/forwarded headers and never use a shared service token for all analysts. Protect backend
and frontend origins from direct access. Terminate TLS at this gateway; private-hop encryption or
an isolated trusted network is required. Restrict proxy-header trust to the gateway IP, never `*`.
The browser stores no API tokens. Gateway session cookies must be Secure, HttpOnly, SameSite=Lax
or Strict, narrowly scoped, short-lived; gateway login/logout/CSRF protection must be verified on
the chosen deployment. API cookies are not accepted as authentication, and disallowed Origin
requests are rejected before mutation. The adapter does not provide immediate JWT revocation;
expiry bounds the revocation window. No live identity-provider integration has been claimed.

Session response is an explicit additive contract extension: `authentication_mode` now accepts
`jwt` and `production_authentication` may be true. The frontend validates the matched pair and
shows a verified-session label. No UI redesign. Existing development contract remains identical.

API: explicit trusted Host and Origin checks, bounded bearer input, no-store responses, request
IDs, nosniff, DENY framing, no-referrer, restrictive API CSP, permissions policy, production HSTS;
production interactive docs disabled. Preflight rejection retains the existing 400 contract.
Frontend: nosniff/frame/permissions/referrer headers and frame/object/base CSP restrictions.
This is not a nonce-based script CSP: Vinext inline hydration requires separate tested integration.
Production proxy target must be explicit and credential-free; browser API requests stay same-origin.
Gateway must repeat security headers on its own errors and enforce TLS/body/header/rate limits.

Implementation references: [PyJWT verification](https://pyjwt.readthedocs.io/en/stable/usage.html)
and [OWASP REST security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html).

## Verification log (in progress)

- Before edits: 20 baseline API/persistence/provider tests passed, 2 upstream warnings.
- Initial sandbox Python/cache access failed; authorized installed-runtime execution succeeded.
- First dependency sync was interrupted by the prior running API executable's Windows file lock.
  Stopped that local preview without touching its data; locked sync then completed.
- Auth/security first run: 29 passed, one existing preflight status regression. Restored its 400
  contract rather than changing the assertion. Existing production test now uses its configured
  trusted HTTPS hostname, retaining all assertions.
- Frontend TypeScript, lint and production build passed after security/session changes.
- Final auth/security milestone: 30 tests passed; Ruff and whitespace checks passed.
- Fresh Python audit including the new JWT/crypto dependencies: no known vulnerabilities;
  local unpublished RingSentinel skipped, audit-tool overlay dependencies included.
- Fresh npm audit succeeded: zero affected packages across the full 702-package reported tree.
  Initial sandbox advisory request failed; authorized official-registry retry succeeded.
