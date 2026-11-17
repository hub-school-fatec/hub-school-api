import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_allowed_origins(origin):
    response = TestClient(app).get("/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers.get("access-control-allow-credentials") is None


def test_disallowed_origin():
    response = TestClient(app).get("/health", headers={"Origin": "https://other.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_authorization_preflight():
    response = TestClient(app).options(
        "/semestres",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "Authorization, Content-Type"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_disallowed_preflight():
    response = TestClient(app).options(
        "/semestres",
        headers={"Origin": "https://other.example", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "Authorization"},
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_wildcard_origin_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_allowed_origins=["*"])
