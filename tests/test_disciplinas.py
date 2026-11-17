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
SEMESTER = UUID("33333333-3333-4333-8333-333333333333")
TEACHER = UUID("44444444-4444-4444-8444-444444444444")
DISCIPLINE = UUID("55555555-5555-4555-8555-555555555555")


def row(owner=USER, teacher=None):
    return {"id": str(DISCIPLINE), "usuario_id": str(owner),
            "semestre_id": str(SEMESTER), "docente_id": str(teacher) if teacher else None,
            "nome": "Matemática", "sigla": "MAT", "carga_horaria_h": "60.5",
            "total_aulas": 80, "frequencia_minima": "75", "media_minima": "6"}


def payload(teacher=None):
    data = {"semestre_id": str(SEMESTER), "nome": " Matemática ", "sigla": " MAT ",
            "carga_horaria_h": "60.5", "total_aulas": 80}
    if teacher is not None:
        data["docente_id"] = str(teacher)
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


def test_authentication_required():
    assert TestClient(app).get("/disciplinas").status_code == 401


def test_empty_list(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.path == "/rest/v1/disciplina"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[])

    assert simulated(handler).get("/disciplinas").json() == []


def test_list_and_filters(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        assert request.url.params["semestre_id"] == f"eq.{SEMESTER}"
        assert request.url.params["docente_id"] == f"eq.{TEACHER}"
        return httpx.Response(200, json=[row(teacher=TEACHER)])

    response = simulated(handler).get(f"/disciplinas?semestre_id={SEMESTER}&docente_id={TEACHER}")
    assert response.status_code == 200
    assert response.json()[0]["id"] == str(DISCIPLINE)


def test_get_by_id(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.params["id"] == f"eq.{DISCIPLINE}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[row()])

    assert simulated(handler).get(f"/disciplinas/{DISCIPLINE}").status_code == 200


@pytest.mark.parametrize("teacher", [None, TEACHER])
def test_create_and_references(simulated, teacher):
    paths = []

    def handler(request):
        check_headers(request)
        paths.append(request.url.path)
        if request.method == "GET":
            assert request.url.params["usuario_id"] == f"eq.{USER}"
            expected_id = SEMESTER if request.url.path.endswith("/semestre") else TEACHER
            assert request.url.params["id"] == f"eq.{expected_id}"
            return httpx.Response(200, json=[{"id": str(expected_id), "usuario_id": str(USER)}])
        assert request.method == "POST" and request.url.path.endswith("/disciplina")
        data = json.loads(request.content)
        assert data["usuario_id"] == str(USER)
        assert data["nome"] == "Matemática" and data["sigla"] == "MAT"
        assert data["carga_horaria_h"] == "60.5"
        assert data["frequencia_minima"] == "75" and data["media_minima"] == "6"
        assert data["docente_id"] == (str(teacher) if teacher else None)
        return httpx.Response(201, json=[row(teacher=teacher)])

    response = simulated(handler).post("/disciplinas", json=payload(teacher))
    assert response.status_code == 201
    assert paths == (["/rest/v1/semestre", "/rest/v1/docente", "/rest/v1/disciplina"]
                     if teacher else ["/rest/v1/semestre", "/rest/v1/disciplina"])


@pytest.mark.parametrize("field,value,expected_path", [
    ("semestre_id", str(SEMESTER), "/rest/v1/semestre"),
    ("docente_id", str(TEACHER), "/rest/v1/docente"),
])
def test_patch_reference(simulated, field, value, expected_path):
    paths = []

    def handler(request):
        check_headers(request)
        paths.append(request.url.path)
        if request.url.path == expected_path:
            return httpx.Response(200, json=[{"id": value, "usuario_id": str(USER)}])
        assert request.url.path == "/rest/v1/disciplina"
        assert request.url.params["id"] == f"eq.{DISCIPLINE}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        if request.method == "PATCH":
            assert json.loads(request.content) == {field: value}
        return httpx.Response(200, json=[row()])

    assert simulated(handler).patch(f"/disciplinas/{DISCIPLINE}", json={field: value}).status_code == 200
    assert paths == ["/rest/v1/disciplina", expected_path, "/rest/v1/disciplina"]


def test_patch_clear_teacher(simulated):
    def handler(request):
        assert request.url.path == "/rest/v1/disciplina"
        if request.method == "PATCH":
            assert json.loads(request.content) == {"docente_id": None}
        return httpx.Response(200, json=[row()])

    assert simulated(handler).patch(f"/disciplinas/{DISCIPLINE}", json={"docente_id": None}).status_code == 200


def test_delete(simulated):
    def handler(request):
        check_headers(request)
        assert request.method == "DELETE"
        assert request.url.params["id"] == f"eq.{DISCIPLINE}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[row()])

    assert simulated(handler).delete(f"/disciplinas/{DISCIPLINE}").status_code == 204


@pytest.mark.parametrize("field,value", [
    ("nome", " "), ("sigla", " "), ("carga_horaria_h", "0"),
    ("carga_horaria_h", "-1"), ("carga_horaria_h", "NaN"),
    ("total_aulas", 0), ("total_aulas", -1), ("total_aulas", 1.5),
    ("frequencia_minima", -1), ("frequencia_minima", 101),
    ("media_minima", -1), ("media_minima", 11),
    ("semestre_id", "invalid"), ("id", str(DISCIPLINE)),
    ("usuario_id", str(USER)), ("criado_em", "2026-01-01T00:00:00Z"),
])
def test_invalid_create(simulated, field, value):
    data = payload()
    data[field] = value
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.post("/disciplinas", json=data).status_code == 422


@pytest.mark.parametrize("data", [{}, {"nome": " "}, {"sigla": " "},
                                    {"semestre_id": None}, {"carga_horaria_h": 0},
                                    {"total_aulas": 0}, {"frequencia_minima": 101},
                                    {"media_minima": 11}, {"id": str(DISCIPLINE)},
                                    {"usuario_id": str(USER)},
                                    {"atualizado_em": "2026-01-01T00:00:00Z"}])
def test_invalid_patch(simulated, data):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.patch(f"/disciplinas/{DISCIPLINE}", json=data).status_code == 422


@pytest.mark.parametrize("table", ["semestre", "docente"])
def test_missing_reference(simulated, table):
    def handler(request):
        if request.url.path == f"/rest/v1/{table}":
            return httpx.Response(200, json=[])
        if table == "docente" and request.url.path.endswith("/semestre"):
            return httpx.Response(200, json=[{"id": str(SEMESTER), "usuario_id": str(USER)}])
        pytest.fail("Unexpected write")

    response = simulated(handler).post("/disciplinas", json=payload(TEACHER))
    assert response.status_code == 404


def test_foreign_reference_rejected(simulated):
    def handler(request):
        if request.url.path.endswith("/semestre"):
            return httpx.Response(200, json=[{"id": str(SEMESTER), "usuario_id": str(OTHER)}])
        pytest.fail("Unexpected write")

    assert simulated(handler).post("/disciplinas", json=payload()).status_code == 404


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_inaccessible_discipline(simulated, method):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    response = client.request(method, f"/disciplinas/{DISCIPLINE}",
                              json={"nome": "Outro"} if method == "PATCH" else None)
    assert response.status_code == 404


def test_foreign_row_rejected(simulated):
    client = simulated(lambda request: httpx.Response(200, json=[row(OTHER)]))
    assert client.get("/disciplinas").status_code == 503


def test_foreign_key_failure_sanitized(simulated):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": str(SEMESTER), "usuario_id": str(USER)}])
        return httpx.Response(400, json={"code": "23503", "message": "private database detail"})

    response = simulated(handler).post("/disciplinas", json=payload())
    assert response.status_code == 422
    assert "private database detail" not in response.text


def test_network_failure(simulated):
    def handler(request):
        raise httpx.ConnectError("private network detail")

    response = simulated(handler).get("/disciplinas")
    assert response.status_code == 503
    assert "private network detail" not in response.text
