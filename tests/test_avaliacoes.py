import json
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
DISCIPLINE = UUID("55555555-5555-4555-8555-555555555555")
EVALUATION = UUID("77777777-7777-4777-8777-777777777777")


def row(owner=USER):
    return {"id": str(EVALUATION), "usuario_id": str(owner),
            "disciplina_id": str(DISCIPLINE), "nome": "Prova",
            "peso": "1", "nota": None, "data_prevista": None}


def payload():
    return {"disciplina_id": str(DISCIPLINE), "nome": " Prova "}


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


def check_headers(request):
    assert request.headers["Authorization"] == "Bearer fake-token"
    assert request.headers["apikey"] == "sb_publishable_fake"


def test_requires_authentication():
    assert TestClient(app).get("/avaliacoes").status_code == 401


def test_empty_list(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.path == "/rest/v1/avaliacao"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[])

    assert simulated(handler).get("/avaliacoes").json() == []


def test_list_filter_and_get(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        if "id" in request.url.params:
            assert request.url.params["id"] == f"eq.{EVALUATION}"
        else:
            assert request.url.params["disciplina_id"] == f"eq.{DISCIPLINE}"
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    assert client.get(f"/avaliacoes?disciplina_id={DISCIPLINE}").status_code == 200
    assert client.get(f"/avaliacoes/{EVALUATION}").json()["id"] == str(EVALUATION)


@pytest.mark.parametrize("optional", [{}, {"nota": None, "data_prevista": None},
                                       {"peso": "2.25", "nota": "8.75", "data_prevista": "2026-12-01"}])
def test_create(simulated, optional):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append(request.url.path)
        if request.method == "GET":
            assert request.url.path == "/rest/v1/disciplina"
            assert request.url.params["id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["usuario_id"] == f"eq.{USER}"
            return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(USER)}])
        assert request.method == "POST" and request.url.path == "/rest/v1/avaliacao"
        data = json.loads(request.content)
        assert data["usuario_id"] == str(USER) and data["nome"] == "Prova"
        assert data["peso"] == optional.get("peso", "1")
        assert data["nota"] == optional.get("nota")
        assert data["data_prevista"] == optional.get("data_prevista")
        return httpx.Response(201, json=[row()])

    response = simulated(handler).post("/avaliacoes", json={**payload(), **optional})
    assert response.status_code == 201
    assert calls == ["/rest/v1/disciplina", "/rest/v1/avaliacao"]


def test_patch_clear_nullable_fields(simulated):
    calls = []

    def handler(request):
        calls.append(request.method)
        assert request.url.path == "/rest/v1/avaliacao"
        assert request.url.params["id"] == f"eq.{EVALUATION}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        if request.method == "PATCH":
            assert json.loads(request.content) == {"nota": None, "data_prevista": None}
        return httpx.Response(200, json=[row()])

    response = simulated(handler).patch(f"/avaliacoes/{EVALUATION}",
                                        json={"nota": None, "data_prevista": None})
    assert response.status_code == 200
    assert calls == ["GET", "PATCH"]


def test_patch_discipline(simulated):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/disciplina"):
            assert request.url.params["id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["usuario_id"] == f"eq.{USER}"
            return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(USER)}])
        if request.method == "PATCH":
            assert json.loads(request.content) == {"disciplina_id": str(DISCIPLINE)}
        return httpx.Response(200, json=[row()])

    assert simulated(handler).patch(f"/avaliacoes/{EVALUATION}",
                                    json={"disciplina_id": str(DISCIPLINE)}).status_code == 200
    assert calls == [("GET", "/rest/v1/avaliacao"), ("GET", "/rest/v1/disciplina"),
                     ("PATCH", "/rest/v1/avaliacao")]


def test_delete(simulated):
    def handler(request):
        check_headers(request)
        assert request.method == "DELETE"
        assert request.url.params["id"] == f"eq.{EVALUATION}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[row()])

    assert simulated(handler).delete(f"/avaliacoes/{EVALUATION}").status_code == 204


@pytest.mark.parametrize("field,value", [
    ("nome", " "), ("peso", "0"), ("peso", "-1"), ("peso", "NaN"),
    ("nota", "-0.1"), ("nota", "10.1"), ("nota", "Infinity"),
    ("data_prevista", "invalid"), ("disciplina_id", "invalid"),
    ("id", str(EVALUATION)), ("usuario_id", str(USER)),
    ("criado_em", "2026-01-01T00:00:00Z"),
])
def test_invalid_create(simulated, field, value):
    data = payload()
    data[field] = value
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.post("/avaliacoes", json=data).status_code == 422


@pytest.mark.parametrize("data", [{}, {"nome": " "}, {"nome": None},
                                    {"peso": None}, {"peso": 0}, {"nota": 11},
                                    {"data_prevista": "bad"}, {"disciplina_id": None},
                                    {"id": str(EVALUATION)}, {"usuario_id": str(USER)},
                                    {"atualizado_em": "2026-01-01T00:00:00Z"}])
def test_invalid_patch(simulated, data):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.patch(f"/avaliacoes/{EVALUATION}", json=data).status_code == 422


def test_missing_discipline(simulated):
    assert simulated(lambda request: httpx.Response(200, json=[])).post(
        "/avaliacoes", json=payload()).status_code == 404


def test_foreign_discipline(simulated):
    def handler(request):
        return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(OTHER)}])

    assert simulated(handler).post("/avaliacoes", json=payload()).status_code == 404


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_inaccessible_evaluation(simulated, method):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    response = client.request(method, f"/avaliacoes/{EVALUATION}",
                              json={"nome": "Outra"} if method == "PATCH" else None)
    assert response.status_code == 404


def test_foreign_row_rejected(simulated):
    client = simulated(lambda request: httpx.Response(200, json=[row(OTHER)]))
    assert client.get("/avaliacoes").status_code == 503


@pytest.mark.parametrize("status,body,expected", [
    (401, {}, 401), (403, {}, 403), (409, {}, 409),
    (400, {"code": "23503", "message": "private detail"}, 422),
    (500, {"message": "private detail"}, 503),
])
def test_postgrest_errors(simulated, status, body, expected):
    response = simulated(lambda request: httpx.Response(status, json=body)).get("/avaliacoes")
    assert response.status_code == expected
    assert "private detail" not in response.text


def test_network_failure(simulated):
    def handler(request):
        raise httpx.ConnectError("private network detail")

    response = simulated(handler).get("/avaliacoes")
    assert response.status_code == 503
    assert "private network detail" not in response.text
