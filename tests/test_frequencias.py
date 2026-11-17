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
FREQUENCY = UUID("88888888-8888-4888-8888-888888888888")


def row(owner=USER, faults=1):
    return {"id": str(FREQUENCY), "usuario_id": str(owner),
            "disciplina_id": str(DISCIPLINE), "data": "2026-11-16",
            "aulas_no_dia": 2, "faltas": faults}


def payload(faults=1):
    return {"disciplina_id": str(DISCIPLINE), "data": "2026-11-16",
            "aulas_no_dia": 2, "faltas": faults}


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
    assert TestClient(app).get("/frequencias").status_code == 401


def test_empty_list(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.path == "/rest/v1/frequencia"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[])

    assert simulated(handler).get("/frequencias").json() == []


def test_list_filters_and_get(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        if "id" in request.url.params:
            assert request.url.params["id"] == f"eq.{FREQUENCY}"
        else:
            assert request.url.params["disciplina_id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["data"] == "eq.2026-11-16"
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    assert client.get(f"/frequencias?disciplina_id={DISCIPLINE}&data=2026-11-16").status_code == 200
    assert client.get(f"/frequencias/{FREQUENCY}").json()["id"] == str(FREQUENCY)


@pytest.mark.parametrize("faults", [0, 1, 2])
def test_create_boundaries(simulated, faults):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append(request.url.path)
        if request.method == "GET":
            assert request.url.path == "/rest/v1/disciplina"
            assert request.url.params["id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["usuario_id"] == f"eq.{USER}"
            return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(USER)}])
        assert request.method == "POST" and request.url.path == "/rest/v1/frequencia"
        data = json.loads(request.content)
        assert data["usuario_id"] == str(USER) and data["faltas"] == faults
        return httpx.Response(201, json=[row(faults=faults)])

    assert simulated(handler).post("/frequencias", json=payload(faults)).status_code == 201
    assert calls == ["/rest/v1/disciplina", "/rest/v1/frequencia"]


def test_patch_combination_valid(simulated):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append(request.method)
        assert request.url.params["id"] == f"eq.{FREQUENCY}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        if request.method == "PATCH":
            assert json.loads(request.content) == {"faltas": 2}
        return httpx.Response(200, json=[row()])

    assert simulated(handler).patch(f"/frequencias/{FREQUENCY}", json={"faltas": 2}).status_code == 200
    assert calls == ["GET", "PATCH"]


@pytest.mark.parametrize("change", [{"faltas": 3}, {"aulas_no_dia": 0},
                                          {"aulas_no_dia": 1, "faltas": 2}])
def test_patch_combination_invalid(simulated, change):
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json=[row()])

    response = simulated(handler).patch(f"/frequencias/{FREQUENCY}", json=change)
    assert response.status_code == 422
    expected_calls = ["GET"] if change == {"faltas": 3} else []
    assert calls == expected_calls


def test_patch_discipline_and_date(simulated):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/disciplina"):
            assert request.url.params["id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["usuario_id"] == f"eq.{USER}"
            return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(USER)}])
        if request.method == "PATCH":
            assert json.loads(request.content) == {"disciplina_id": str(DISCIPLINE), "data": "2026-11-17"}
        return httpx.Response(200, json=[row()])

    response = simulated(handler).patch(f"/frequencias/{FREQUENCY}",
                                        json={"disciplina_id": str(DISCIPLINE), "data": "2026-11-17"})
    assert response.status_code == 200
    assert calls == [("GET", "/rest/v1/frequencia"), ("GET", "/rest/v1/disciplina"),
                     ("PATCH", "/rest/v1/frequencia")]


def test_delete(simulated):
    def handler(request):
        check_headers(request)
        assert request.method == "DELETE"
        assert request.url.params["id"] == f"eq.{FREQUENCY}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[row()])

    assert simulated(handler).delete(f"/frequencias/{FREQUENCY}").status_code == 204


@pytest.mark.parametrize("field,value", [
    ("aulas_no_dia", 0), ("aulas_no_dia", -1), ("aulas_no_dia", 1.5),
    ("faltas", -1), ("faltas", 3), ("faltas", 1.5),
    ("data", "2026-02-30"), ("disciplina_id", "bad"),
    ("id", str(FREQUENCY)), ("usuario_id", str(USER)),
    ("criado_em", "2026-01-01T00:00:00Z"),
])
def test_invalid_create(simulated, field, value):
    data = payload()
    data[field] = value
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.post("/frequencias", json=data).status_code == 422


@pytest.mark.parametrize("data", [{}, {"faltas": None}, {"faltas": -1},
                                    {"aulas_no_dia": None}, {"disciplina_id": None},
                                    {"data": "bad"}, {"id": str(FREQUENCY)},
                                    {"usuario_id": str(USER)},
                                    {"atualizado_em": "2026-01-01T00:00:00Z"}])
def test_invalid_patch(simulated, data):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.patch(f"/frequencias/{FREQUENCY}", json=data).status_code == 422


def test_invalid_filter(simulated):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.get("/frequencias?data=2026-02-30").status_code == 422


@pytest.mark.parametrize("owner", [None, OTHER])
def test_missing_or_foreign_discipline(simulated, owner):
    rows = [] if owner is None else [{"id": str(DISCIPLINE), "usuario_id": str(owner)}]
    assert simulated(lambda request: httpx.Response(200, json=rows)).post(
        "/frequencias", json=payload()).status_code == 404


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_inaccessible_frequency(simulated, method):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    response = client.request(method, f"/frequencias/{FREQUENCY}",
                              json={"faltas": 0} if method == "PATCH" else None)
    assert response.status_code == 404


def test_foreign_row_rejected(simulated):
    assert simulated(lambda request: httpx.Response(200, json=[row(OTHER)])).get(
        "/frequencias").status_code == 503


@pytest.mark.parametrize("status,body,expected", [
    (409, {}, 409), (400, {"code": "23505", "message": "private detail"}, 409),
    (400, {"code": "23503", "message": "private detail"}, 422),
    (500, {"message": "private detail"}, 503),
])
def test_postgrest_errors(simulated, status, body, expected):
    response = simulated(lambda request: httpx.Response(status, json=body)).get("/frequencias")
    assert response.status_code == expected
    assert "private detail" not in response.text


def test_network_failure(simulated):
    def handler(request):
        raise httpx.ConnectError("private network detail")

    response = simulated(handler).get("/frequencias")
    assert response.status_code == 503
    assert "private network detail" not in response.text


@pytest.mark.parametrize("code,expected", [
    ("23514", "23514"), ("23502", "23502"), ("23503", "23503"),
    ("22007", "22007"), ("22008", "22008"), ("22P02", "22P02"),
    ("private-token-like-code", "unknown"),
])
def test_local_postgrest_diagnostic_is_safe(simulated, monkeypatch, caplog, code, expected):
    monkeypatch.setenv("HUB_SCHOOL_LOCAL_POSTGREST_DIAGNOSTICS", "1")
    private = "private-response-or-token"

    def handler(request):
        if request.url.path == "/rest/v1/disciplina":
            return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(USER)}])
        return httpx.Response(400, json={"code": code, "message": private, "details": private})

    with caplog.at_level("WARNING", logger="uvicorn.error"):
        response = simulated(handler).post("/frequencias", json=payload())
    assert response.status_code == (422 if code != "private-token-like-code" else 503)
    assert f"table=frequencia method=POST http_status=400 db_code={expected}" in caplog.text
    assert private not in caplog.text + response.text
    assert str(USER) not in caplog.text


def test_local_postgrest_diagnostic_requires_opt_in(simulated, monkeypatch, caplog):
    monkeypatch.delenv("HUB_SCHOOL_LOCAL_POSTGREST_DIAGNOSTICS", raising=False)

    def handler(request):
        if request.url.path == "/rest/v1/disciplina":
            return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(USER)}])
        return httpx.Response(400, json={"code": "23514", "message": "private"})

    with caplog.at_level("WARNING", logger="uvicorn.error"):
        response = simulated(handler).post("/frequencias", json=payload())
    assert response.status_code == 422
    assert "postgrest_diagnostic" not in caplog.text
