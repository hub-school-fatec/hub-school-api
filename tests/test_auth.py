from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core import security
from app.main import app


@pytest.fixture
def auth(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = jwt.algorithms.ECAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update(kid="test-key", alg="ES256", use="sig")
    settings = Settings(_env_file=None, supabase_url="https://test.supabase.co",
                        supabase_jwt_issuer="https://test.supabase.co/auth/v1")
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "_get_jwks", lambda url: {"keys": [jwk]})

    def make_token(**changes):
        now = datetime.now(timezone.utc)
        claims = {"sub": "user-1", "iss": settings.supabase_jwt_issuer,
                  "aud": "authenticated", "iat": now, "exp": now + timedelta(minutes=5)}
        claims.update(changes)
        return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key"})

    return make_token


def test_health_public():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_missing_token():
    assert TestClient(app).get("/auth/me").status_code == 401


def test_invalid_token(auth):
    assert TestClient(app).get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_valid_token(auth):
    token = auth()
    response = TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1"}


@pytest.mark.parametrize("claims", [
    {"exp": datetime.now(timezone.utc) - timedelta(seconds=10)},
    {"iss": "https://other.supabase.co/auth/v1"},
    {"aud": "anon"},
    {"sub": ""},
    {"iat": datetime.now(timezone.utc) + timedelta(seconds=8)},
])
def test_invalid_claims(auth, claims):
    token = auth(**claims)
    response = TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert token not in response.text


def test_clock_leeway(auth):
    token = auth(iat=datetime.now(timezone.utc) + timedelta(seconds=4))
    assert TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_missing_kid(auth):
    key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode({"sub": "user-1"}, key, algorithm="ES256")
    assert TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_wrong_algorithm(auth):
    token = jwt.encode({"sub": "user-1"}, "x" * 32, algorithm="HS256", headers={"kid": "test-key"})
    assert TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_invalid_signature(auth):
    token = auth()
    key = ec.generate_private_key(ec.SECP256R1())
    claims = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key"})
    assert TestClient(app).get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_missing_configuration(monkeypatch):
    monkeypatch.setattr(security, "get_settings", lambda: Settings(_env_file=None))
    assert TestClient(app).get("/health").status_code == 200
    assert TestClient(app).get("/auth/me", headers={"Authorization": "Bearer fake"}).status_code == 401


def test_jwks_cache(monkeypatch):
    security._jwks_cache.clear()
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return httpx.Response(200, json={"keys": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(security.httpx, "get", fake_get)
    security._get_jwks("https://test.supabase.co")
    security._get_jwks("https://test.supabase.co")
    assert len(calls) == 1
