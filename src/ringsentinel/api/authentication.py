"""Operator-selected public-key verification, with bounded rotating-key retrieval."""

import hashlib
import json
import threading
import time
import urllib.request

import jwt

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.service import Principal
from ringsentinel.platform.settings import Settings


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_public_keys(url: str) -> bytes:
    # Fixed operator configuration only. Never fetch token jku/x5u or follow redirects.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    deadline = time.monotonic() + 4
    with opener.open(request, timeout=2) as response:
        if response.status != 200:
            raise ValueError("Key endpoint unavailable")
        body = bytearray()
        while True:
            if time.monotonic() >= deadline:
                raise ValueError("Key retrieval deadline exceeded")
            part = response.read1(min(8192, 65537 - len(body)))
            body.extend(part)
            if len(body) > 65536:
                raise ValueError("Key response too large")
            if not part:
                return bytes(body)


def parse_public_keys(payload: bytes):
    if len(payload) > 65536:
        raise ValueError("Key response too large")
    data = json.loads(payload)
    items = data["keys"]
    if not isinstance(items, list) or not 1 <= len(items) <= 32:
        raise ValueError("Invalid key set size")
    keys = {}
    for item in items:
        if (
            item.get("kty") != "RSA"
            or item.get("alg", "RS256") != "RS256"
            or item.get("use", "sig") != "sig"
            or item.get("key_ops", ["verify"]) != ["verify"]
            or not isinstance(item.get("kid"), str)
            or not 1 <= len(item["kid"]) <= 256
            or item["kid"] in keys
            or any(field in item for field in ("d", "p", "q", "dp", "dq", "qi", "oth"))
        ):
            raise ValueError("Invalid verification key")
        key = jwt.PyJWK.from_dict(item).key
        if not 2048 <= key.key_size <= 8192:
            raise ValueError("Unsupported RSA key size")
        keys[item["kid"]] = key
    return keys


class TokenVerifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.keys = {}
        self._lock = threading.Lock()
        self._expires = 0.0
        self._next_refresh = 0.0
        if settings.auth_jwks_url:
            return  # Lazy retrieval: provider outages do not break unrelated cold starts.
        try:
            with settings.auth_jwks_path.open("rb") as source:
                self.keys = parse_public_keys(source.read(65537))
        except Exception:
            # Key material, file paths, and parser exception strings are not public/log fields.
            raise ValueError("Unable to load configured public JWT verification keys") from None

    def _key(self, kid: str):
        if not isinstance(kid, str) or not 1 <= len(kid) <= 256:
            raise ValueError("Invalid key identifier")
        if not self.settings.auth_jwks_url:
            return self.keys[kid]
        with self._lock:
            now = time.monotonic()
            if now < self._expires and kid in self.keys:
                return self.keys[kid]
            if now >= self._next_refresh:
                # One refresh per process per 30s, even for arbitrary unknown kids.
                self._next_refresh = now + 30
                try:
                    keys = parse_public_keys(fetch_public_keys(self.settings.auth_jwks_url))
                except Exception:
                    raise ValueError("Public key retrieval unavailable") from None
                self.keys = keys  # Atomic replacement removes retired keys.
                self._expires = time.monotonic() + self.settings.auth_jwks_cache_seconds
            if time.monotonic() >= self._expires:
                raise ValueError("Public key cache expired")
            return self.keys[kid]

    def verify(self, authorization: str) -> Principal:
        try:
            scheme, token = authorization.split(" ", 1)
            if scheme.lower() != "bearer" or len(token) > 16384:
                raise ValueError("Invalid bearer token")
            header = jwt.get_unverified_header(token)
            # No jku/x5u discovery, algorithm negotiation, or token-supplied keys.
            if header.get("alg") != "RS256" or header.get("crit"):
                raise ValueError("Unsupported token")
            claims = jwt.decode(
                token,
                self._key(header["kid"]),
                algorithms=["RS256"],
                issuer=self.settings.auth_issuer,
                audience=self.settings.auth_audience,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub"]},
            )
            if (
                any(type(claims[k]) is not int for k in ("exp", "iat", "nbf"))
                or not isinstance(claims["sub"], str)
                or not 1 <= len(claims["sub"]) <= 512
                or not 0 < claims["exp"] - claims["iat"] <= self.settings.auth_max_token_seconds
                or claims["nbf"] > claims["exp"]
            ):
                raise ValueError("Invalid claims")
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise ProductError("UNAUTHORIZED") from None
        scope = claims.get("scope")
        if not isinstance(scope, str) or self.settings.auth_required_scope not in scope.split():
            raise ProductError("FORBIDDEN")
        # Stable issuer+subject identity, never email or a caller-selected database ID.
        identity = json.dumps([claims["iss"], claims["sub"]], separators=(",", ":"))
        return Principal("jwt_" + hashlib.sha256(identity.encode()).hexdigest())
