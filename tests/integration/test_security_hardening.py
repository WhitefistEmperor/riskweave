"""Real RSA signatures, fail-closed configuration, host/origin and log boundaries."""

import json
import logging
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from ringsentinel.api.app import create_app
from ringsentinel.platform.database import Database
from ringsentinel.platform.settings import Settings


@pytest.fixture
def authenticated(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-key", alg="RS256", use="sig")
    path = tmp_path / "public-jwks.json"
    path.write_text(json.dumps({"keys": [jwk]}))
    settings = Settings(
        environment="production",
        auth_mode="jwt",
        demo_enabled=False,
        jobs_enabled=False,
        auth_jwks_path=path,
        auth_issuer="https://issuer.example",
        auth_audience="ringsentinel",
        frontend_origins=["https://analyst.example"],
        database_url=f"sqlite:///{tmp_path / 'db'}",
        storage_root=tmp_path / "objects",
    )
    db = Database(settings.database_url.get_secret_value())
    db.migrate()
    db.engine.dispose()

    def token(**changes):
        now = int(time.time())
        claims = dict(
            iss=settings.auth_issuer,
            aud=settings.auth_audience,
            sub="alice",
            iat=now,
            nbf=now,
            exp=now + 300,
            scope="ringsentinel:analyst",
        )
        claims.update(changes)
        claims = {name: value for name, value in claims.items() if value is not None}
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})

    with TestClient(create_app(settings=settings), base_url="https://analyst.example") as client:
        yield client, token, settings


def test_signed_authentication_owner_isolation_and_no_client_identity(authenticated):
    client, token, _ = authenticated
    client.headers["Authorization"] = f"Bearer {token()}"
    session = client.get("/api/v1/session").json()
    assert session["production_authentication"] is True
    assert session["authentication_mode"] == "jwt"
    assert session["user_id"].startswith("jwt_")
    client.headers["X-Development-User"] = "victim"
    assert client.get("/api/v1/session").json() == session
    inv = client.post("/api/v1/investigations", json={"name": "Owned"}).json()["id"]
    client.headers["Authorization"] = f"Bearer {token(sub='bob')}"
    assert client.get("/api/v1/investigations").json() == []
    for suffix in ("", "/artifacts", "/runs"):
        assert client.get(f"/api/v1/investigations/{inv}{suffix}").status_code == 404
    client.headers["Authorization"] = f"Bearer {token(scope='unrelated')}"
    assert client.get("/api/v1/session").status_code == 403


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": 1},
        {"iss": "https://evil.example"},
        {"aud": "other"},
        {"sub": ""},
        {"nbf": 9999999999},
        {"iat": 9999999999},
        {"exp": 9999999999},
        {"exp": "9999999999"},
    ],
)
def test_invalid_signed_claims_are_unauthorized(authenticated, claims):
    client, token, _ = authenticated
    response = client.get("/api/v1/session", headers={"Authorization": f"Bearer {token(**claims)}"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_missing_forged_cookie_algorithm_and_unknown_key_rejected(authenticated):
    client, token, _ = authenticated
    valid = token()
    claims = jwt.decode(valid, options={"verify_signature": False})
    forged = jwt.encode(
        claims, "not-a-real-secret" * 3, algorithm="HS256", headers={"kid": "test-key"}
    )
    none = jwt.encode(claims, "", algorithm="none", headers={"kid": "test-key"})
    for credential in (
        "",
        "Bearer fake",
        f"Bearer {valid[:-12]}invalidvalue",
        f"Bearer {forged}",
        f"Bearer {none}",
        "Basic dGVzdA==",
        "Bearer " + "a" * 17000,
    ):
        response = client.get("/api/v1/session", headers={"Authorization": credential})
        assert response.status_code == 401
    assert client.get("/api/v1/session", headers={"Cookie": f"token={valid}"}).status_code == 401


def test_security_headers_origins_hosts_health_safe_logs(authenticated, caplog):
    client, token, _ = authenticated
    caplog.set_level(logging.INFO, logger="ringsentinel.http")
    secret = token()
    client.headers["Authorization"] = f"Bearer {secret}"
    for path in ("/api/v1/health", "/api/v1/ready", "/api/v1/session", "/missing"):
        response = client.get(path)
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
        assert response.headers["X-Request-ID"]
        assert "set-cookie" not in response.headers
    assert client.get("/api/v1/health", headers={"Host": "evil.example"}).status_code == 400
    assert (
        client.post(
            "/api/v1/investigations",
            json={"name": "Denied"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    allowed = client.options(
        "/api/v1/session",
        headers={
            "Origin": "https://analyst.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert allowed.status_code == 200
    assert client.get("/docs").status_code == 404
    assert secret not in caplog.text
    assert "Denied" not in caplog.text


def test_missing_invalid_auth_configuration_fails_closed(tmp_path):
    with pytest.raises(ValueError):
        Settings(environment="production")
    with pytest.raises(ValueError):
        Settings(auth_mode="jwt")
    path = tmp_path / "bad.json"
    path.write_text('{"keys": []}')
    settings = Settings(
        auth_mode="jwt",
        auth_jwks_path=path,
        auth_issuer="https://issuer.example",
        auth_audience="ringsentinel",
    )
    with pytest.raises(ValueError, match="public JWT"):
        create_app(settings=settings)
    with pytest.raises(ValueError):
        Settings(trusted_hosts=["*"])


def test_missing_claims_and_unknown_signer_fail_closed(authenticated):
    client, token, _ = authenticated
    for field in ("exp", "iat", "nbf", "sub", "iss", "aud"):
        response = client.get(
            "/api/v1/session", headers={"Authorization": f"Bearer {token(**{field: None})}"}
        )
        assert response.status_code == 401
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = jwt.decode(token(), options={"verify_signature": False})
    for kid in ("unknown-key", "test-key"):
        signed = jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})
        assert (
            client.get("/api/v1/session", headers={"Authorization": f"Bearer {signed}"}).status_code
            == 401
        )


def test_production_explicit_storage_and_startup_log_allowlist(authenticated, caplog):
    _, _, settings = authenticated
    with pytest.raises(ValueError, match="explicit database"):
        Settings(
            environment="production",
            auth_mode="jwt",
            demo_enabled=False,
            frontend_origins=settings.frontend_origins,
            auth_jwks_path=settings.auth_jwks_path,
            auth_issuer=settings.auth_issuer,
            auth_audience=settings.auth_audience,
        )
    caplog.set_level(logging.INFO, logger="ringsentinel.operations")
    with TestClient(create_app(settings=settings), base_url="https://analyst.example"):
        pass
    records = [json.loads(r.message) for r in caplog.records if r.name == "ringsentinel.operations"]
    assert records[-1]["event"] == "startup"
    assert records[-1]["authentication"] == "jwt"
    assert str(settings.storage_root) not in caplog.text
    assert settings.database_url.get_secret_value() not in caplog.text
