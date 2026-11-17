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
SCHEDULE = UUID("66666666-6666-4666-8666-666666666666")


def row(owner=USER):
    return {"id": str(SCHEDULE), "usuario_id": str(owner), "disciplina_id": str(DISCIPLINE),
            "dia_semana": 2, "hora_inicio": "08:00:00", "hora_fim": "09:30:00",
            "sala": "A1", "aulas_no_dia": 2}


def payload():
    return {"disciplina_id": str(DISCIPLINE), "dia_semana": 2,
            "hora_inicio": "08:00", "hora_fim": "09:30", "sala": " A1 ",
            "aulas_no_dia": 2}


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
    assert TestClient(app).get("/horarios-aula").status_code == 401


def test_empty_list(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.path == "/rest/v1/horario_aula"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[])

    assert simulated(handler).get("/horarios-aula").json() == []


def test_list_filters_and_get(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        if "id" in request.url.params:
            assert request.url.params["id"] == f"eq.{SCHEDULE}"
        else:
            assert request.url.params["disciplina_id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["dia_semana"] == "eq.2"
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    assert client.get(f"/horarios-aula?disciplina_id={DISCIPLINE}&dia_semana=2").status_code == 200
    assert client.get(f"/horarios-aula/{SCHEDULE}").json()["id"] == str(SCHEDULE)


def test_create_and_reference(simulated):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append(request.url.path)
        if request.method == "GET":
            assert request.url.path == "/rest/v1/disciplina"
            assert request.url.params["id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["usuario_id"] == f"eq.{USER}"
            return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(USER)}])
        assert request.method == "POST" and request.url.path == "/rest/v1/horario_aula"
        data = json.loads(request.content)
        assert data["usuario_id"] == str(USER)
        assert data["sala"] == "A1" and data["aulas_no_dia"] == 2
        return httpx.Response(201, json=[row()])

    assert simulated(handler).post("/horarios-aula", json=payload()).status_code == 201
    assert calls == ["/rest/v1/disciplina", "/rest/v1/horario_aula"]


def test_create_default_aulas(simulated):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(USER)}])
        assert json.loads(request.content)["aulas_no_dia"] == 1
        return httpx.Response(201, json=[row()])

    data = payload()
    del data["aulas_no_dia"]
    assert simulated(handler).post("/horarios-aula", json=data).status_code == 201


def test_patch_room_and_times(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.path == "/rest/v1/horario_aula"
        assert request.url.params["id"] == f"eq.{SCHEDULE}"
        if request.method == "PATCH":
            assert json.loads(request.content) == {"hora_fim": "10:00:00", "sala": "B2"}
        return httpx.Response(200, json=[row()])

    response = simulated(handler).patch(f"/horarios-aula/{SCHEDULE}",
                                        json={"hora_fim": "10:00", "sala": " B2 "})
    assert response.status_code == 200


def test_patch_discipline(simulated):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/rest/v1/disciplina":
            assert request.url.params["id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["usuario_id"] == f"eq.{USER}"
            return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(USER)}])
        return httpx.Response(200, json=[row()])

    assert simulated(handler).patch(f"/horarios-aula/{SCHEDULE}",
                                    json={"disciplina_id": str(DISCIPLINE)}).status_code == 200
    assert calls == [("GET", "/rest/v1/horario_aula"), ("GET", "/rest/v1/disciplina"),
                     ("PATCH", "/rest/v1/horario_aula")]


def test_patch_invalid_combined_times(simulated):
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json=[row()])

    assert simulated(handler).patch(f"/horarios-aula/{SCHEDULE}",
                                    json={"hora_inicio": "10:00"}).status_code == 422
    assert calls == ["GET"]


def test_delete(simulated):
    def handler(request):
        check_headers(request)
        assert request.method == "DELETE"
        assert request.url.params["id"] == f"eq.{SCHEDULE}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[row()])

    assert simulated(handler).delete(f"/horarios-aula/{SCHEDULE}").status_code == 204


@pytest.mark.parametrize("field,value", [
    ("dia_semana", 0), ("dia_semana", 8), ("dia_semana", "2"),
    ("hora_inicio", "invalid"), ("hora_fim", "07:00"),
    ("hora_fim", "08:00"), ("sala", "  "),
    ("aulas_no_dia", 0), ("aulas_no_dia", -1), ("aulas_no_dia", 1.5),
    ("disciplina_id", "invalid"), ("id", str(SCHEDULE)),
    ("usuario_id", str(USER)), ("criado_em", "2026-01-01T00:00:00Z"),
])
def test_invalid_create(simulated, field, value):
    data = payload()
    data[field] = value
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.post("/horarios-aula", json=data).status_code == 422


@pytest.mark.parametrize("data", [{}, {"sala": " "}, {"hora_inicio": None},
                                    {"hora_inicio": "12:00", "hora_fim": "11:00"},
                                    {"dia_semana": 8}, {"aulas_no_dia": 0},
                                    {"disciplina_id": None}, {"id": str(SCHEDULE)},
                                    {"usuario_id": str(USER)},
                                    {"atualizado_em": "2026-01-01T00:00:00Z"}])
def test_invalid_patch(simulated, data):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.patch(f"/horarios-aula/{SCHEDULE}", json=data).status_code == 422


def test_invalid_filter(simulated):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.get("/horarios-aula?dia_semana=8").status_code == 422


def test_missing_or_foreign_discipline(simulated):
    def handler(request):
        return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(OTHER)}])

    assert simulated(handler).post("/horarios-aula", json=payload()).status_code == 404


def test_missing_discipline(simulated):
    assert simulated(lambda request: httpx.Response(200, json=[])).post(
        "/horarios-aula", json=payload()).status_code == 404


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_inaccessible_schedule(simulated, method):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    response = client.request(method, f"/horarios-aula/{SCHEDULE}",
                              json={"sala": "B2"} if method == "PATCH" else None)
    assert response.status_code == 404


def test_foreign_row_rejected(simulated):
    client = simulated(lambda request: httpx.Response(200, json=[row(OTHER)]))
    assert client.get("/horarios-aula").status_code == 503


@pytest.mark.parametrize("status,body,expected", [
    (409, {}, 409), (400, {"code": "23505"}, 409),
    (400, {"code": "23503", "message": "private detail"}, 422),
    (500, {"message": "private detail"}, 503),
])
def test_postgrest_errors(simulated, status, body, expected):
    response = simulated(lambda request: httpx.Response(status, json=body)).get("/horarios-aula")
    assert response.status_code == expected
    assert "private detail" not in response.text


def test_network_failure(simulated):
    def handler(request):
        raise httpx.ConnectError("private network detail")

    response = simulated(handler).get("/horarios-aula")
    assert response.status_code == 503
    assert "private network detail" not in response.text
