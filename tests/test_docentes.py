from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.main import app
from app.repositories import supabase
from app.routers.semestres import get_http_client


USER = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")
TEACHER = UUID("44444444-4444-4444-8444-444444444444")


def row(owner=USER):
    return {"id": str(TEACHER), "usuario_id": str(owner), "nome": "Ada",
            "email": "ada@example.test", "telefone": None, "observacoes": None}


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


def check_request(request, method, by_id=False):
    assert request.method == method
    assert request.url.path == "/rest/v1/docente"
    assert request.headers["apikey"] == "sb_publishable_fake"
    assert request.headers["Authorization"] == "Bearer fake-token"
    if method != "POST":
        assert request.url.params["usuario_id"] == f"eq.{USER}"
    if by_id:
        assert request.url.params["id"] == f"eq.{TEACHER}"


def test_authentication_required():
    assert TestClient(app).get("/docentes").status_code == 401


def test_empty_list(simulated):
    def handler(request):
        check_request(request, "GET")
        return httpx.Response(200, json=[])

    assert simulated(handler).get("/docentes").json() == []


def test_list_and_get(simulated):
    def handler(request):
        check_request(request, "GET", by_id="id" in request.url.params)
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    assert client.get("/docentes").json()[0]["id"] == str(TEACHER)
    assert client.get(f"/docentes/{TEACHER}").status_code == 200


def test_create(simulated):
    def handler(request):
        check_request(request, "POST")
        assert request.content == (b'{"nome":"Ada","email":"ada@example.test",'
                                   b'"telefone":null,"observacoes":null,'
                                   b'"usuario_id":"11111111-1111-4111-8111-111111111111"}')
        return httpx.Response(201, json=[row()])

    response = simulated(handler).post("/docentes", json={"nome": " Ada ", "email": " ada@example.test "})
    assert response.status_code == 201
    assert response.json()["nome"] == "Ada"


def test_patch_and_delete(simulated):
    def handler(request):
        check_request(request, request.method, by_id=True)
        if request.method == "PATCH":
            assert request.content == b'{"telefone":"123"}'
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    assert client.patch(f"/docentes/{TEACHER}", json={"telefone": "123"}).status_code == 200
    assert client.delete(f"/docentes/{TEACHER}").status_code == 204


@pytest.mark.parametrize("payload", [
    {"nome": " ", "email": "ada@example.test"},
    {"nome": "Ada", "email": " "},
    {"nome": "Ada", "email": "not-an-email"},
    {"nome": "Ada", "email": "ada@example.test", "usuario_id": str(OTHER)},
    {"nome": "Ada", "email": "ada@example.test", "id": str(TEACHER)},
    {"nome": "Ada", "email": "ada@example.test", "criado_em": "2026-01-01T00:00:00Z"},
])
def test_invalid_create(simulated, payload):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.post("/docentes", json=payload).status_code == 422


@pytest.mark.parametrize("payload", [{}, {"nome": "  "}, {"email": "bad"},
                                      {"email": None}, {"id": str(TEACHER)},
                                      {"usuario_id": str(USER)}, {"atualizado_em": "2026-01-01T00:00:00Z"}])
def test_invalid_patch(simulated, payload):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.patch(f"/docentes/{TEACHER}", json=payload).status_code == 422


def test_invalid_uuid(simulated):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.get("/docentes/not-a-uuid").status_code == 422


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_inaccessible_record(simulated, method):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    response = client.request(method, f"/docentes/{TEACHER}",
                              json={"nome": "Novo"} if method == "PATCH" else None)
    assert response.status_code == 404


def test_foreign_row_rejected(simulated):
    client = simulated(lambda request: httpx.Response(200, json=[row(OTHER)]))
    assert client.get("/docentes").status_code == 503


@pytest.mark.parametrize("status,body,expected", [
    (401, {}, 401), (403, {}, 403), (409, {}, 409),
    (400, {"code": "23505"}, 409), (500, {}, 503),
])
def test_postgrest_errors(simulated, status, body, expected):
    client = simulated(lambda request: httpx.Response(status, json=body))
    assert client.get("/docentes").status_code == expected


def test_network_failure(simulated):
    def handler(request):
        raise httpx.ConnectError("private detail")

    response = simulated(handler).get("/docentes")
    assert response.status_code == 503
    assert "private detail" not in response.text
