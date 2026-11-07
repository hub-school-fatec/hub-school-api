import io
import json
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm

from app.core.config import settings
from app.core.security import get_jwks_client
from app.main import app


def test_real_client_cache_rotation_and_expiry(monkeypatch):
    keys = [ec.generate_private_key(ec.SECP256R1()) for _ in range(2)]
    jwks = []
    for i, key in enumerate(keys):
        item = json.loads(ECAlgorithm.to_jwk(key.public_key()))
        item.update(kid=str(i), alg='ES256', use='sig')
        jwks.append(item)
    calls = []
    current = {'index': 0}

    def urlopen(*args, **kwargs):
        calls.append(True)
        return io.BytesIO(json.dumps({'keys': [jwks[current['index']]]}).encode())

    monkeypatch.setattr('urllib.request.OpenerDirector.open', urlopen)
    monkeypatch.setattr(settings, 'supabase_url', 'https://example.supabase.co')
    monkeypatch.setattr(settings, 'supabase_jwt_issuer', 'https://example.supabase.co/auth/v1')
    jwks_client = get_jwks_client(settings.supabase_url + '/auth/v1/.well-known/jwks.json',
                                 settings.jwks_cache_seconds, settings.jwks_timeout_seconds)

    def token(index):
        return jwt.encode({'sub': 'A', 'iss': settings.supabase_jwt_issuer, 'aud': 'authenticated',
                           'exp': datetime.now(timezone.utc) + timedelta(minutes=5)},
                          keys[index], algorithm='ES256', headers={'kid': str(index)})

    with TestClient(app) as client:
        def check(index):
            return client.get('/auth/me', headers={'Authorization': 'Bearer ' + token(index)})
        assert check(0).status_code == 200
        assert check(0).status_code == 200
        assert len(calls) == 1
        current['index'] = 1
        # A new kid during PyJWT's cooldown is rejected without repeated fetches.
        assert check(1).status_code == 401
        assert len(calls) == 1
        jwks_client._last_successful_fetch -= jwks_client.cooldown_duration + 1
        assert check(1).status_code == 200
        assert len(calls) == 2
        jwks_client = get_jwks_client(settings.supabase_url + '/auth/v1/.well-known/jwks.json',
                                     settings.jwks_cache_seconds, settings.jwks_timeout_seconds)
        monkeypatch.setattr(jwks_client.jwk_set_cache, 'is_expired', lambda: True)
        assert check(1).status_code == 200
        assert len(calls) == 3
        assert check(0).status_code == 401
