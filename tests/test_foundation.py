from fastapi.testclient import TestClient

from app.main import app


def test_foundation():
    with TestClient(app) as client:
        assert client.get('/health').json() == {'status': 'ok'}
        assert client.get('/docs').status_code == 200
        assert client.get('/auth/me').status_code == 401
        spec = client.get('/openapi.json').json()
        assert spec['paths']['/auth/me']['get']['security']
