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
public JWKS file and analyst scope. Its current verifier requires integer `iat`,
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

Browser scripting remains a trust boundary: deploy an appropriate script CSP and
keep third-party scripts out of the analyst workspace. Current CSP restricts framing,
objects and base URI; a full script CSP remains outstanding.
