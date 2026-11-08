# Authentication key rotation

JWT mode accepts exactly one configured source: an offline public JWKS file or
`RINGSENTINEL_AUTH_JWKS_URL`. The latter must be a fixed HTTPS endpoint without
credentials, query, fragment or nonstandard port. Select it from the identity
provider's trusted configuration; token `jku`/`x5u` headers never choose a URL.
TLS certificate verification remains enabled, redirects and environment proxies
are disabled, and no access tokens or cookies are sent to the key endpoint.

Remote keys are fetched lazily. Each API process caches them for
`RINGSENTINEL_AUTH_JWKS_CACHE_SECONDS` (300 by default, range 60–900).
A previously unknown key may trigger an earlier refresh, with at most one
attempt per 30 seconds per process. Concurrent requests share a refresh lock.
The endpoint has a two-second socket timeout, a four-second response-read budget,
a 64 KiB response cap and a 32-key limit. DNS resolution depends on the host
resolver; the read budget is not a guaranteed total network deadline.

Only public RSA verification keys of 2048–8192 bits are admitted. Duplicate IDs,
private RSA components, incompatible algorithms/use/operations and malformed
documents are rejected. Optional `alg`/`use` fields may be omitted by a provider;
actual token verification remains fixed to RS256. Issuer, audience, scope,
required claims and token lifetime checks are unchanged.

Successful refresh atomically replaces the complete set, including removal of
retired keys. Refresh failure never extends expiry. Unexpired known keys can
continue validating tokens, while unknown or expired keys fail with the normal
safe 401 response. Failed retrievals are throttled too. A legitimate new key can
therefore receive 401 for up to the remaining 30-second cooldown; publish new
public keys before issuing tokens with them.

For routine rotation, publish old and new keys together, wait at least the
configured cache interval plus rollout/network allowance, then begin signing
with the new key. Keep the old public key for the maximum outstanding token
lifetime plus clock allowance before removing it. Retired keys may remain
usable until each process's cache expires. This is bounded key rotation, not
immediate per-user session revocation. Emergency revocation requires provider
action and forced cache/process replacement or an additional revocation layer.

Offline-file mode still requires an explicit restart after replacing the file.
Neither mode issues tokens or provisions an identity provider. Local tests use
real RSA signatures for overlap, removal, identity stability, expired-cache
outages, recovery and concurrent unknown-key requests; transport tests verify
response caps and redirect rejection. Live HTTPS provider rotation, login,
expiry, scope denial and two-user isolation remain release requirements.
