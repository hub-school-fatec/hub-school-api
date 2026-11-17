import httpx
import pytest
from fastapi.testclient import TestClient
from uuid import UUID

from app.core.config import Settings
from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.main import app
from app.repositories import supabase
from app.routers.semestres import get_http_client


USER = UUID("11111111-1111-4111-8111-111111111111")


@pytest.fixture
def simulated(monkeypatch):
    settings = Settings(_env_file=None, supabase_url="https://test.supabase.co",
                        supabase_jwt_issuer="https://test.supabase.co/auth/v1",
                        supabase_publishable_key="sb_publishable_fake")
    monkeypatch.setattr(supabase, "get_settings", lambda: settings)
    app.dependency_overrides[get_authenticated_identity] = lambda: AuthenticatedIdentity(USER, "fake-token")
    clients = []

    def configure(handler):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        clients.append(client)
        app.dependency_overrides[get_http_client] = lambda: client
        return TestClient(app)

    yield configure
    app.dependency_overrides.clear()
    for client in clients:
        client.close()


def test_authentication_required():
    assert TestClient(app).get("/calendario-academico").status_code == 401


def test_empty_calendar(simulated):
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/rest/v1/calendario_academico"
        assert request.url.params["select"] == "id,data,tipo,descricao"
        assert "usuario_id" not in request.url.params
        assert request.headers["Authorization"] == "Bearer fake-token"
        assert request.headers["apikey"] == "sb_publishable_fake"
        return httpx.Response(200, json=[])

    assert simulated(handler).get("/calendario-academico").json() == []


def test_calendar_list(simulated):
    rows = [{"id": "item-1", "data": "2026-11-17", "tipo": "feriado", "descricao": "Evento acadêmico"}]
    client = simulated(lambda request: httpx.Response(200, json=rows))
    response = client.get("/calendario-academico")
    assert response.status_code == 200
    assert response.json() == rows


@pytest.mark.parametrize("status,expected", [(401, 401), (403, 403), (500, 503)])
def test_http_errors(simulated, status, expected):
    client = simulated(lambda request: httpx.Response(status, text="sensitive-provider-message"))
    response = client.get("/calendario-academico")
    assert response.status_code == expected
    assert "sensitive-provider-message" not in response.text


def test_invalid_response(simulated):
    client = simulated(lambda request: httpx.Response(200, json=[{"id": "item-1"}]))
    assert client.get("/calendario-academico").status_code == 503


def test_network_error(simulated):
    def handler(request):
        raise httpx.ConnectError("sensitive-provider-message", request=request)

    response = simulated(handler).get("/calendario-academico")
    assert response.status_code == 503
    assert "sensitive-provider-message" not in response.text


def test_openapi_registration():
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    assert set(paths["/calendario-academico"]) == {"get"}
