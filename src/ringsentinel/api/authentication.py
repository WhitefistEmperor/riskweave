"""Offline, pinned public-key access-token verification; no token issuance or cookies."""

import hashlib
import json

import jwt

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.service import Principal
from ringsentinel.platform.settings import Settings


class TokenVerifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        try:
            data = json.loads(settings.auth_jwks_path.read_text(encoding="utf-8"))
            self.keys = {}
            for item in data["keys"]:
                if (
                    item.get("kty") != "RSA"
                    or item.get("alg") != "RS256"
                    or item.get("use") != "sig"
                    or not isinstance(item.get("kid"), str)
                    or not item["kid"]
                    or item["kid"] in self.keys
                    or "d" in item
                ):
                    raise ValueError("Invalid verification key")
                key = jwt.PyJWK.from_dict(item).key
                if key.key_size < 2048:
                    raise ValueError("RSA key too small")
                self.keys[item["kid"]] = key
            if not self.keys:
                raise ValueError("Empty key set")
        except Exception:
            # Key material, file paths, and parser exception strings are not public/log fields.
            raise ValueError("Unable to load configured public JWT verification keys") from None

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
                self.keys[header["kid"]],
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
