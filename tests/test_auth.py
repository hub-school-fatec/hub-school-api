import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.core.config import settings
from app.core.security import PyJWKClient
from app.main import app


client = TestClient(app)


@pytest.fixture
def token_factory(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    other_private_key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "test-key", "alg": "ES256", "use": "sig"})

    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(
        settings,
        "supabase_jwt_issuer",
        "https://example.supabase.co/auth/v1",
    )
    monkeypatch.setattr(
        PyJWKClient,
        "fetch_data",
        lambda self: {"keys": [public_jwk]},
    )

    def create_token(
        *,
        signing_key=private_key,
        exp=None,
        issuer="https://example.supabase.co/auth/v1",
        audience="authenticated",
        subject="user-123",
        omit=None,
        kid='test-key',
        algorithm='ES256',
    ):
        if exp is None:
            exp = datetime.now(timezone.utc) + timedelta(minutes=5)
        payload = {
            "sub": subject,
            "iss": issuer,
            "aud": audience,
            "exp": exp,
        }
        if omit:
            payload.pop(omit)
        return jwt.encode(
            payload,
            signing_key,
            algorithm=algorithm,
            headers={"kid": kid} if kid is not None else {},
        )

    return create_token, other_private_key


def test_missing_token_returns_401():
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_invalid_token_returns_401(token_factory):
    token, _ = token_factory

    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


def test_invalid_signature_returns_401(token_factory):
    create_token, other_private_key = token_factory

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {create_token(signing_key=other_private_key)}"},
    )

    assert response.status_code == 401


def test_expired_token_returns_401(token_factory):
    create_token, _ = token_factory

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {create_token(exp=datetime.now(timezone.utc) - timedelta(minutes=1))}"
        },
    )

    assert response.status_code == 401


def test_wrong_issuer_returns_401(token_factory):
    create_token, _ = token_factory

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {create_token(issuer='https://wrong.example.com')}"},
    )

    assert response.status_code == 401


def test_wrong_audience_returns_401(token_factory):
    create_token, _ = token_factory

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {create_token(audience='wrong-audience')}"},
    )

    assert response.status_code == 401


def test_valid_token_returns_user_id(token_factory):
    create_token, _ = token_factory

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {create_token()}"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-123"}


@pytest.mark.parametrize('claim', ['exp', 'iss', 'aud', 'sub'])
def test_required_claims(token_factory, claim):
    create_token, _ = token_factory
    response = client.get('/auth/me', headers={'Authorization': f'Bearer {create_token(omit=claim)}'})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'


@pytest.mark.parametrize('subject', ['', '  ', 42, None])
def test_invalid_subject(token_factory, subject):
    create_token, _ = token_factory
    assert client.get('/auth/me', headers={'Authorization': f'Bearer {create_token(subject=subject)}'}).status_code == 401


@pytest.mark.parametrize('kid', [None, '', 'unknown'])
def test_invalid_kid(token_factory, kid):
    create_token, _ = token_factory
    assert client.get('/auth/me', headers={'Authorization': f'Bearer {create_token(kid=kid)}'}).status_code == 401


def test_wrong_algorithm():
    token = jwt.encode({'sub': 'A'}, 'test-only-secret-that-is-at-least-32-bytes', algorithm='HS256', headers={'kid': 'x'})
    assert client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_wrong_scheme():
    assert client.get('/auth/me', headers={'Authorization': 'Basic abc'}).status_code == 401


def test_jwks_connection_failure(token_factory, monkeypatch):
    create_token, _ = token_factory
    def fail(self):
        raise jwt.PyJWKClientConnectionError('sensitive internal location')
    monkeypatch.setattr(PyJWKClient, 'fetch_data', fail)
    response = client.get('/auth/me', headers={'Authorization': f'Bearer {create_token()}'} )
    assert response.status_code == 401
    assert 'sensitive' not in response.text


def test_validated_jwt_controls_resource_ownership(token_factory):
    from app.repositories.base import get_repository
    from tests.fakes import MemoryRepository

    create_token, _ = token_factory
    repo = MemoryRepository()
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        headers = {u: {'Authorization': 'Bearer ' + create_token(subject=u)} for u in ('A', 'B')}
        payload = dict(nome='2026/2', data_inicio='2026-08-01', data_fim='2026-12-01', ativo=True)
        records = {}
        for user in ('A', 'B'):
            response = client.post('/semestres', json=payload, headers=headers[user])
            assert response.status_code == 201
            records[user] = response.json()['id']
        for owner, foreign in [('A', 'B'), ('B', 'A')]:
            assert client.get('/semestres/' + records[owner], headers=headers[owner]).status_code == 200
            assert client.get('/semestres/' + records[foreign], headers=headers[owner]).status_code == 404
            assert client.put('/semestres/' + records[foreign], json=payload, headers=headers[owner]).status_code == 404
    finally:
        app.dependency_overrides.clear()
