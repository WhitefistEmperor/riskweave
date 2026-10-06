# Investigation session privacy

When OIDC is configured, the investigation layout checks the stored user before
mounting private workspace components. An already-expired or missing user sees
the sign-in screen without requesting private API data. The real oidc-client-ts
access-token-expired and user-unloaded events unmount the whole private subtree,
including case state, graph instances and effects. Existing effect cleanup aborts
pending reads and stops polling. Expiry requires no additional API request.

Sign-out unmounts the workspace before provider discovery or redirect completes.
The library then removes its sessionStorage user and attempts provider sign-out.
A provider error leaves the workspace inactive and displays a return-to-sign-in
link. The error message does not promise that provider-side logout or revocation
succeeded. No token or private evidence is added to localStorage. API JWT, scope
and owner checks remain authoritative; the UI boundary does not authorize access.
Development mode without OIDC retains its existing behavior.

Explicit sign-out also publishes a literal signed-out signal using a same-origin
[BroadcastChannel](https://developer.mozilla.org/en-US/docs/Web/API/Broadcast_Channel_API).
Other open workspace tabs invalidate their boundary, unmount private data and
remove their own stored user before provider completion. The channel carries no
credentials, user/case IDs or evidence, and creates no persistent localStorage
marker. It closes on unmount. Initial user-check completion cannot reactivate a
boundary invalidated by expiry, user unload or a sign-out signal. Browser policy
may disable channels; local cleanup still applies but cross-tab synchronization
is not claimed when channels are unavailable.

## Browser controls

`frontend/tests/session-boundary.spec.ts` uses the actual library's user storage
and expiry timer with synthetic stored tokens, fixture private API responses and
paused/failed local issuer discovery. It checks that:

- Already-expired sessions mount/request no private workspace.
- Idle expiry removes loaded case data without another API request.
- Sign-out removes private content while provider discovery is still pending,
  clears the local user, and keeps content hidden when discovery fails.
- Two open same-origin tabs both clear private content and their own user stores
  before provider discovery completes; provider failure keeps both hidden.

These are session UI controls, not live issuer or JWT signature proof. The usual
production-browser suite explicitly skips them; CI runs them separately against
an isolated OIDC-configured production build after the normal suite.

From the repository root, with installed frontend dependencies:

```text
uv run --no-sync python scripts/prepare_auth_browser_fixture.py work/new-session-ui
```

The destination must be new and under ignored `work/`; existing fixtures/cases are
never overwritten. The helper excludes environment files, output and cache
directories. It creates internal dependency paths using hard-linked immutable
installed package files so Turbopack accepts its filesystem root. Do not install,
update or edit packages inside this fixture; dependency updates belong in the
source frontend. Fixture caches and build outputs are separate.

Inside the new fixture, configure only synthetic local test values:

```text
NEXT_PUBLIC_RISKWEAVE_OIDC_AUTHORITY=http://127.0.0.1:5174/fixture-issuer
NEXT_PUBLIC_RISKWEAVE_OIDC_CLIENT_ID=riskweave-session-browser-control
RINGSENTINEL_ENVIRONMENT=test
```

Build with `npm run build`, then start on port5174 with
`node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 5174`.
From the source frontend, set `RISKWEAVE_OIDC_BROWSER_TEST=1` and
`RINGSENTINEL_UI_URL=http://127.0.0.1:5174`, then run
`npx playwright test tests/session-boundary.spec.ts`. Set variables using the
current shell's normal syntax; these are not production issuer settings.

## Remaining hosted proof

Verify the exact deployed HTTPS source with the actual configured issuer:
authorization-code/PKCE callback, token expiry, rejected/revoked sessions, provider
logout success and failure, stale tabs/back navigation, owner isolation and no
private requests after expiry. Open same-origin tabs are covered by the dedicated two-tab control when channels
are available. Closed/suspended tabs, blocked channels and provider-session
revocation still require hosted verification. Browser expiry cleanup cannot revoke server tokens.
The deployment and identity release gates remain open until that evidence exists.
