"""Real signatures exercise rotation, revocation, bounded cache and outage behavior."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from ringsentinel.api import authentication as auth
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.settings import Settings


@pytest.fixture
def rotation(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: clock[0])
    keys = [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)]
    documents = []
    for index, key in enumerate(keys):
        public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
        public.update(kid=str(index))  # Standards-compliant optional alg/use omitted.
        documents.append(public)
    response = [json.dumps({"keys": documents[:1]}).encode()]
    calls = []

    def fetch(url):
        calls.append(url)
        if isinstance(response[0], Exception):
            raise response[0]
        return response[0]

    monkeypatch.setattr(auth, "fetch_public_keys", fetch)
    verifier = auth.TokenVerifier(
        Settings(
            auth_mode="jwt",
            auth_jwks_url="https://issuer.example/keys",
            auth_issuer="https://issuer.example",
            auth_audience="riskweave",
            auth_jwks_cache_seconds=60,
        )
    )

    def bearer(index=0, **headers):
        now = int(time.time())
        claims = dict(
            iss="https://issuer.example",
            aud="riskweave",
            sub="alice",
            iat=now,
            nbf=now,
            exp=now + 300,
            scope="ringsentinel:analyst",
        )
        return "Bearer " + jwt.encode(
            claims, keys[index], algorithm="RS256", headers={"kid": str(index), **headers}
        )

    return verifier, bearer, response, documents, clock, calls


def test_rotation_replaces_keys_without_restart_and_preserves_identity(rotation):
    verifier, bearer, response, documents, clock, calls = rotation
    owner = verifier.verify(bearer())
    response[0] = json.dumps({"keys": documents}).encode()
    clock[0] += 31
    assert verifier.verify(bearer(1)) == owner
    response[0] = json.dumps({"keys": documents[1:]}).encode()
    clock[0] += 61
    assert verifier.verify(bearer(1)) == owner
    with pytest.raises(ProductError):
        verifier.verify(bearer())
    assert len(calls) == 3


def test_outage_never_extends_expired_keys_and_recovers_after_cooldown(rotation):
    verifier, bearer, response, documents, clock, calls = rotation
    verifier.verify(bearer())
    response[0] = OSError("private upstream failure")
    clock[0] += 61
    for _ in range(10):
        with pytest.raises(ProductError) as error:
            verifier.verify(bearer())
        assert error.value.code == "UNAUTHORIZED"
    assert len(calls) == 2
    response[0] = json.dumps({"keys": documents}).encode()
    clock[0] += 31
    verifier.verify(bearer(1))


def test_parallel_unknown_keys_cannot_create_refresh_storm(rotation):
    verifier, bearer, _, _, clock, calls = rotation
    verifier.verify(bearer())
    clock[0] += 31

    def denied(index):
        with pytest.raises(ProductError):
            verifier.verify(bearer(kid=f"unknown-{index}"))

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(denied, range(40)))
    assert len(calls) == 2


def test_token_url_headers_never_select_key_endpoint(rotation):
    verifier, bearer, _, _, _, calls = rotation
    verifier.verify(bearer(jku="https://evil.invalid/keys", x5u="http://127.0.0.1"))
    assert calls == ["https://issuer.example/keys"]


@pytest.mark.parametrize("mutation", ["private", "duplicate", "encryption", "operations", "size"])
def test_malformed_remote_keys_fail_closed(rotation, mutation):
    verifier, bearer, response, documents, _, _ = rotation
    key = dict(documents[0])
    data = [key]
    if mutation == "private":
        key["p"] = "private-component"
    elif mutation == "duplicate":
        data.append(dict(key))
    elif mutation == "encryption":
        key["use"] = "enc"
    elif mutation == "operations":
        key["key_ops"] = ["sign"]
    else:
        response[0] = b" " * 65537
    if mutation != "size":
        response[0] = json.dumps({"keys": data}).encode()
    with pytest.raises(ProductError):
        verifier.verify(bearer())


@pytest.mark.parametrize(
    "url",
    [
        "http://issuer.example/keys",
        "https://u:p@issuer.example/keys",
        "https://issuer.example:8443/keys",
        "https://issuer.example/keys#other",
    ],
)
def test_remote_configuration_rejects_unsafe_endpoints(url):
    with pytest.raises(ValueError):
        Settings(
            auth_mode="jwt",
            auth_jwks_url=url,
            auth_issuer="https://issuer.example",
            auth_audience="riskweave",
        )


def test_static_and_remote_key_sources_cannot_be_combined(tmp_path):
    with pytest.raises(ValueError):
        Settings(
            auth_mode="jwt",
            auth_jwks_url="https://issuer.example/keys",
            auth_jwks_path=tmp_path / "keys",
            auth_issuer="https://issuer.example",
            auth_audience="riskweave",
        )


def test_transport_bounds_response_and_refuses_redirects():
    # Loopback HTTP isolates transport behavior. Settings rejects HTTP in deployments.
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from urllib.error import HTTPError

    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/unexpected")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"x" * (65537 if self.path == "/large" else 12))

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        assert auth.fetch_public_keys(origin + "/small") == b"x" * 12
        with pytest.raises(ValueError, match="too large"):
            auth.fetch_public_keys(origin + "/large")
        with pytest.raises(HTTPError) as error:
            auth.fetch_public_keys(origin + "/redirect")
        assert error.value.code == 302
        assert "/unexpected" not in hits
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
