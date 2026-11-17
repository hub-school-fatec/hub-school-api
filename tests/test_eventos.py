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
OTHER_DISCIPLINE = UUID("99999999-9999-4999-8999-999999999999")
SCHEDULE = UUID("66666666-6666-4666-8666-666666666666")
EVENT = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def row(owner=USER, **changes):
    data = {"id": str(EVENT), "usuario_id": str(owner), "disciplina_id": str(DISCIPLINE),
            "horario_aula_id": None, "data_aula": None, "tipo": "prova",
            "titulo": "Prova", "descricao": None, "inicio": "2026-11-16T10:00:00+00:00",
            "fim": "2026-11-16T11:00:00+00:00", "sala": None,
            "cancelado": False, "lembrete_ativo": True, "antecedencias_minutos": [30]}
    data.update(changes)
    return data


def payload(**changes):
    data = {"disciplina_id": str(DISCIPLINE), "tipo": "prova", "titulo": " Prova ",
            "inicio": "2026-11-16T10:00:00Z", "fim": "2026-11-16T11:00:00Z",
            "cancelado": False, "lembrete_ativo": True, "antecedencias_minutos": [30]}
    data.update(changes)
    return data


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


def reference_response(request, *, schedule_discipline=DISCIPLINE, owner=USER):
    check_headers(request)
    assert request.url.params["usuario_id"] == f"eq.{USER}"
    if request.url.path.endswith("/disciplina"):
        assert request.url.params["id"] == f"eq.{DISCIPLINE}"
        return httpx.Response(200, json=[{"id": str(DISCIPLINE), "usuario_id": str(owner)}])
    assert request.url.path.endswith("/horario_aula")
    assert request.url.params["id"] == f"eq.{SCHEDULE}"
    return httpx.Response(200, json=[{"id": str(SCHEDULE), "usuario_id": str(owner),
                                      "disciplina_id": str(schedule_discipline)}])


def test_requires_authentication():
    assert TestClient(app).get("/eventos").status_code == 401


def test_empty_list(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.path == "/rest/v1/evento"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[])

    assert simulated(handler).get("/eventos").json() == []


def test_list_filters_and_get(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        if "id" in request.url.params:
            assert request.url.params["id"] == f"eq.{EVENT}"
        else:
            assert request.url.params["disciplina_id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["tipo"] == "eq.prova"
            assert request.url.params["cancelado"] == "eq.false"
            assert request.url.params["inicio"].startswith("gte.2026-11-16T00:00:00")
            assert request.url.params["fim"].startswith("lte.2026-11-17T00:00:00")
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    params = {"disciplina_id": str(DISCIPLINE), "tipo": "prova", "cancelado": "false",
              "inicio": "2026-11-16T00:00:00Z", "fim": "2026-11-17T00:00:00Z"}
    assert client.get("/eventos", params=params).status_code == 200
    assert client.get(f"/eventos/{EVENT}").json()["id"] == str(EVENT)


@pytest.mark.parametrize("kind", ["prova", "trabalho", "apresentacao", "aula", "evento"])
def test_create_types(simulated, kind):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append(request.url.path)
        if request.method == "GET":
            return reference_response(request)
        assert request.method == "POST" and request.url.path == "/rest/v1/evento"
        data = json.loads(request.content)
        assert data["usuario_id"] == str(USER) and data["titulo"] == "Prova"
        assert data["tipo"] == kind
        return httpx.Response(201, json=[row(tipo=kind)])

    assert simulated(handler).post("/eventos", json=payload(tipo=kind)).status_code == 201
    assert calls == ["/rest/v1/disciplina", "/rest/v1/evento"]


def test_create_without_discipline(simulated):
    def handler(request):
        check_headers(request)
        assert request.method == "POST"
        assert json.loads(request.content)["disciplina_id"] is None
        return httpx.Response(201, json=[row(disciplina_id=None)])

    response = simulated(handler).post("/eventos", json=payload(disciplina_id=None))
    assert response.status_code == 201


def test_create_with_schedule(simulated):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.method == "GET":
            return reference_response(request)
        assert json.loads(request.content)["horario_aula_id"] == str(SCHEDULE)
        return httpx.Response(201, json=[row(tipo="aula", horario_aula_id=str(SCHEDULE),
                                             data_aula="2026-11-16")])

    data = payload(tipo="aula", horario_aula_id=str(SCHEDULE), data_aula="2026-11-16")
    assert simulated(handler).post("/eventos", json=data).status_code == 201
    assert calls == ["/rest/v1/disciplina", "/rest/v1/horario_aula", "/rest/v1/evento"]


@pytest.mark.parametrize("change", [
    {"horario_aula_id": str(SCHEDULE), "tipo": "aula", "data_aula": None},
    {"horario_aula_id": str(SCHEDULE), "tipo": "prova", "data_aula": "2026-11-16"},
    {"tipo": "outro"}, {"titulo": "  "},
    {"inicio": "2026-11-16T10:00:00"}, {"fim": "2026-11-16T11:00:00"},
    {"fim": "2026-11-16T09:59:00Z"},
    {"antecedencias_minutos": [-1]}, {"antecedencias_minutos": [1.5]},
    {"id": str(EVENT)}, {"usuario_id": str(USER)},
    {"criado_em": "2026-11-16T10:00:00Z"},
])
def test_invalid_create(simulated, change):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.post("/eventos", json=payload(**change)).status_code == 422


@pytest.mark.parametrize("params", [
    {"inicio": "2026-11-16T10:00:00"},
    {"fim": "2026-11-16T10:00:00"},
    {"inicio": "2026-11-17T00:00:00Z", "fim": "2026-11-16T00:00:00Z"},
    {"tipo": "outro"},
])
def test_invalid_filters(simulated, params):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.get("/eventos", params=params).status_code == 422


def test_schedule_discipline_mismatch(simulated):
    def handler(request):
        if request.url.path.endswith("/horario_aula"):
            return reference_response(request, schedule_discipline=OTHER_DISCIPLINE)
        if request.url.path.endswith("/disciplina"):
            return reference_response(request)
        pytest.fail("Unexpected write")

    data = payload(tipo="aula", horario_aula_id=str(SCHEDULE), data_aula="2026-11-16")
    assert simulated(handler).post("/eventos", json=data).status_code == 422


@pytest.mark.parametrize("path", ["/disciplina", "/horario_aula"])
def test_missing_reference(simulated, path):
    def handler(request):
        if request.url.path.endswith(path):
            return httpx.Response(200, json=[])
        if request.method == "GET":
            return reference_response(request)
        pytest.fail("Unexpected write")

    data = payload(tipo="aula", horario_aula_id=str(SCHEDULE), data_aula="2026-11-16")
    assert simulated(handler).post("/eventos", json=data).status_code == 404


def test_foreign_reference(simulated):
    def handler(request):
        return reference_response(request, owner=OTHER)

    assert simulated(handler).post("/eventos", json=payload()).status_code == 404


def test_patch_clear_optionals(simulated):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/disciplina"):
            return reference_response(request)
        if request.method == "PATCH":
            assert json.loads(request.content) == {"disciplina_id": None, "descricao": None,
                                                   "fim": None, "sala": None, "data_aula": None}
        return httpx.Response(200, json=[row()])

    data = {"disciplina_id": None, "descricao": None, "fim": None,
            "sala": None, "data_aula": None}
    assert simulated(handler).patch(f"/eventos/{EVENT}", json=data).status_code == 200
    assert calls == [("GET", "/rest/v1/evento"), ("PATCH", "/rest/v1/evento")]


def test_patch_final_state_rejects_schedule_without_date(simulated):
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json=[row(tipo="aula", horario_aula_id=str(SCHEDULE),
                                             data_aula="2026-11-16")])

    assert simulated(handler).patch(f"/eventos/{EVENT}", json={"data_aula": None}).status_code == 422
    assert calls == ["GET"]


def test_patch_final_state_rejects_non_class_type(simulated):
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json=[row(tipo="aula", horario_aula_id=str(SCHEDULE),
                                             data_aula="2026-11-16")])

    assert simulated(handler).patch(f"/eventos/{EVENT}", json={"tipo": "prova"}).status_code == 422
    assert calls == ["GET"]


def test_patch_clear_existing_schedule(simulated):
    calls = []

    def handler(request):
        calls.append(request.method)
        if request.url.path.endswith("/disciplina"):
            return reference_response(request)
        if request.method == "PATCH":
            assert json.loads(request.content) == {"horario_aula_id": None, "data_aula": None}
            return httpx.Response(200, json=[row(tipo="aula", horario_aula_id=None, data_aula=None)])
        return httpx.Response(200, json=[row(tipo="aula", horario_aula_id=str(SCHEDULE),
                                             data_aula="2026-11-16")])

    data = {"horario_aula_id": None, "data_aula": None}
    assert simulated(handler).patch(f"/eventos/{EVENT}", json=data).status_code == 200
    assert calls == ["GET", "GET", "PATCH"]


def test_patch_final_interval_rejected(simulated):
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json=[row()])

    assert simulated(handler).patch(f"/eventos/{EVENT}",
                                    json={"inicio": "2026-11-16T12:00:00Z"}).status_code == 422
    assert calls == ["GET"]


def test_patch_schedule_link(simulated):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/disciplina") or request.url.path.endswith("/horario_aula"):
            return reference_response(request)
        return httpx.Response(200, json=[row()])

    data = {"tipo": "aula", "horario_aula_id": str(SCHEDULE), "data_aula": "2026-11-16"}
    assert simulated(handler).patch(f"/eventos/{EVENT}", json=data).status_code == 200
    assert calls == [("GET", "/rest/v1/evento"), ("GET", "/rest/v1/disciplina"),
                     ("GET", "/rest/v1/horario_aula"), ("PATCH", "/rest/v1/evento")]


@pytest.mark.parametrize("change", [{}, {"titulo": " "}, {"tipo": None},
                                      {"inicio": None}, {"fim": "2026-11-16T11:00:00"},
                                      {"antecedencias_minutos": None},
                                      {"antecedencias_minutos": [-1]},
                                      {"atualizado_em": "2026-11-16T10:00:00Z"}])
def test_invalid_patch(simulated, change):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.patch(f"/eventos/{EVENT}", json=change).status_code == 422


def test_delete(simulated):
    def handler(request):
        check_headers(request)
        assert request.method == "DELETE"
        assert request.url.params["id"] == f"eq.{EVENT}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[row()])

    assert simulated(handler).delete(f"/eventos/{EVENT}").status_code == 204


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_inaccessible_event(simulated, method):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    response = client.request(method, f"/eventos/{EVENT}",
                              json={"titulo": "Outro"} if method == "PATCH" else None)
    assert response.status_code == 404


def test_foreign_row_rejected(simulated):
    assert simulated(lambda request: httpx.Response(200, json=[row(OTHER)])).get(
        "/eventos").status_code == 503


def test_duplicate_schedule_and_date(simulated):
    def handler(request):
        if request.method == "GET":
            return reference_response(request)
        assert request.method == "POST"
        return httpx.Response(409, json={"code": "23505", "message": "private detail"})

    data = payload(tipo="aula", horario_aula_id=str(SCHEDULE), data_aula="2026-11-16")
    response = simulated(handler).post("/eventos", json=data)
    assert response.status_code == 409
    assert "private detail" not in response.text


@pytest.mark.parametrize("status,body,expected", [
    (409, {}, 409), (400, {"code": "23505", "message": "private detail"}, 409),
    (400, {"code": "23503", "message": "private detail"}, 422),
    (500, {"message": "private detail"}, 503),
])
def test_postgrest_errors(simulated, status, body, expected):
    response = simulated(lambda request: httpx.Response(status, json=body)).get("/eventos")
    assert response.status_code == expected
    assert "private detail" not in response.text


def test_network_failure(simulated):
    def handler(request):
        raise httpx.ConnectError("private network detail")

    response = simulated(handler).get("/eventos")
    assert response.status_code == 503
    assert "private network detail" not in response.text
