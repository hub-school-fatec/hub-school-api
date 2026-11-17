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
SEMESTER = UUID("33333333-3333-4333-8333-333333333333")


def row(owner=USER):
    return {"id": str(SEMESTER), "usuario_id": str(owner), "nome": "2026.1",
            "data_inicio": "2026-01-01", "data_fim": "2026-06-30", "ativo": False}


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


def check_request(request, method):
    assert request.method == method
    assert request.url.path == "/rest/v1/semestre"
    assert request.headers["apikey"] == "sb_publishable_fake"
    assert request.headers["Authorization"] == "Bearer fake-token"
    if method != "POST":
        assert request.url.params["usuario_id"] == f"eq.{USER}"


def test_no_authentication():
    assert TestClient(app).get("/semestres").status_code == 401


def test_empty_list(simulated):
    client = simulated(lambda request: (check_request(request, "GET"), httpx.Response(200, json=[]))[1])
    assert client.get("/semestres").json() == []


def test_list_and_get(simulated):
    def handler(request):
        check_request(request, "GET")
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    assert client.get("/semestres").json()[0]["id"] == str(SEMESTER)
    assert client.get(f"/semestres/{SEMESTER}").status_code == 200


def test_create(simulated):
    def handler(request):
        check_request(request, "POST")
        assert b'"usuario_id":"11111111-1111-4111-8111-111111111111"' in request.content
        return httpx.Response(201, json=[row()])

    client = simulated(handler)
    assert client.post("/semestres", json={"nome": "2026.1", "data_inicio": "2026-01-01",
                                           "data_fim": "2026-06-30"}).status_code == 201


def test_patch_and_delete(simulated):
    def handler(request):
        check_request(request, request.method)
        if request.method == "PATCH":
            assert request.content == b'{"nome":"Novo"}'
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    assert client.patch(f"/semestres/{SEMESTER}", json={"nome": "Novo"}).status_code == 200
    assert client.delete(f"/semestres/{SEMESTER}").status_code == 204


@pytest.mark.parametrize("payload", [
    {"nome": " ", "data_inicio": "2026-01-01", "data_fim": "2026-06-30"},
    {"nome": "A", "data_inicio": "2026-06-30", "data_fim": "2026-01-01"},
    {"nome": "A", "data_inicio": "invalid", "data_fim": "2026-06-30"},
    {"nome": "A", "data_inicio": "2026-01-01", "data_fim": "2026-06-30", "usuario_id": str(OTHER)},
    {"nome": "A", "data_inicio": "2026-01-01", "data_fim": "2026-06-30", "ativo": "true"},
])
def test_invalid_create(simulated, payload):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.post("/semestres", json=payload).status_code == 422


def test_invalid_patch(simulated):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.patch(f"/semestres/{SEMESTER}", json={"id": str(OTHER)}).status_code == 422


@pytest.mark.parametrize("method,path", [
    ("GET", f"/semestres/{SEMESTER}"),
    ("PATCH", f"/semestres/{SEMESTER}"),
    ("DELETE", f"/semestres/{SEMESTER}"),
])
def test_inaccessible_record(simulated, method, path):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    response = client.request(method, path, json={"nome": "Novo"} if method == "PATCH" else None)
    assert response.status_code == 404


def test_foreign_row_rejected(simulated):
    client = simulated(lambda request: httpx.Response(200, json=[row(OTHER)]))
    assert client.get("/semestres").status_code == 503


@pytest.mark.parametrize("status,body,expected", [
    (409, {}, 409), (400, {"code": "23505"}, 409),
    (400, {"code": "23514"}, 422), (500, {}, 503),
])
def test_postgrest_errors(simulated, status, body, expected):
    client = simulated(lambda request: httpx.Response(status, json=body))
    assert client.get("/semestres").status_code == expected


def test_network_failure(simulated):
    def handler(request):
        raise httpx.ConnectError("private detail")

    client = simulated(handler)
    response = client.get("/semestres")
    assert response.status_code == 503
    assert "private detail" not in response.text


def test_reject_privileged_key(simulated, monkeypatch):
    settings = Settings(_env_file=None, supabase_url="https://test.supabase.co",
                        supabase_jwt_issuer="https://test.supabase.co/auth/v1",
                        supabase_publishable_key="sb_secret_fake")
    monkeypatch.setattr(supabase, "get_settings", lambda: settings)
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.get("/semestres").status_code == 503
