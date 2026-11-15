# Browser analyst sign-in

Set these nonsecret variables when building the frontend:

```text
NEXT_PUBLIC_RISKWEAVE_OIDC_AUTHORITY=https://your-identity-provider/your-issuer
NEXT_PUBLIC_RISKWEAVE_OIDC_CLIENT_ID=riskweave-analyst
```

Configure a public OIDC client using authorization code with PKCE (S256), and exact
redirect `${FRONTEND_ORIGIN}/auth/callback`, post-logout `${FRONTEND_ORIGIN}/sign-in`
and web origin `${FRONTEND_ORIGIN}`. Do not embed a client secret in the browser.
The requested scope is `openid profile ringsentinel:analyst`. Disable implicit and
password grants and self-registration for an invite-only analyst installation.

The API must run with production JWT authentication and the same issuer, API audience,
public JWKS source and analyst scope. Choose exactly one of
`RINGSENTINEL_AUTH_JWKS_PATH` (offline file) or `RINGSENTINEL_AUTH_JWKS_URL`
(operator-selected HTTPS endpoint). The rotating endpoint is described in
[authentication key rotation](authentication-key-rotation.md).
The verifier requires integer `iat`,
`nbf` and `exp` claims, subject, issuer and audience; access-token lifetime must not
exceed `RINGSENTINEL_AUTH_MAX_TOKEN_SECONDS` (900 seconds by default). Configure your
provider accordingly. Public verification keys are not signing credentials. Follow
the existing key-rotation procedure when changing provider keys.

The browser library validates the OIDC redirect state and exchanges the code using
PKCE. It uses tab-scoped session storage. Access tokens are sent only through the
configured same-origin API gateway; they never appear in a URL or local storage.
No offline-access scope is requested. Missing or expired tokens return to sign-in;
API 401s also return to sign-in. Logout clears the local user and invokes provider
logout. A provider logout failure is shown explicitly, so clearing local credentials
is not confused with successfully ending the provider session.

Live provider testing is still required: sign in, logout, expiry, provider rejection,
tampered callback/state, scope denial and two-user ownership isolation. The existing
offline signed-token API tests are evidence of verification and authorization only.
This frontend change does not provision an identity provider by itself.

Browser documents now receive a fresh cryptographic CSP nonce for framework
hydration. Inline handlers and scripts without trusted provenance are blocked;
production does not allow script `unsafe-inline` or `unsafe-eval`. Connections
are restricted to the app and the configured issuer origin. If discovery lists
token/key endpoints on another origin, configure `RINGSENTINEL_OIDC_CONNECT_ORIGINS`
as a JSON array of exact HTTPS origins (at most eight additional origins).
Set this backend-only frontend variable at build and runtime. Do not use wildcard
origins. API rewrites remain same-origin browser requests.

All document routes render dynamically and use private/no-store responses so
nonces are not reused by static output or shared caching. This increases server
requests relative to static pages; verify the free hosting allowance. Styles still
permit inline positioning used by the component libraries. Third-party scripts,
iframes and provider widgets are not enabled; use the full-page PKCE flow.
Production-browser tests cover framework hydration, fresh/non-caller-selected
nonces, HTML script/handler injection and blocked unconfigured connections. The
chosen live provider and hosted gateway must still pass their full workflow.
