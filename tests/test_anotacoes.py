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
EVENT = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOTE = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SELECT = "id,usuario_id,disciplina_id,evento_id,titulo,corpo,criado_em,atualizado_em"


def row(owner=USER, discipline=None, event=None, body="Texto"):
    return {"id": str(NOTE), "usuario_id": str(owner),
            "disciplina_id": str(discipline) if discipline else None,
            "evento_id": str(event) if event else None,
            "titulo": "Resumo", "corpo": body}


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
    assert TestClient(app).get("/anotacoes").status_code == 401


def test_empty_list(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.path == "/rest/v1/anotacao"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        assert request.url.params["select"] == SELECT
        return httpx.Response(200, json=[])

    assert simulated(handler).get("/anotacoes").json() == []


def test_list_filters_and_get(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        assert request.url.params["select"] == SELECT
        if "id" in request.url.params:
            assert request.url.params["id"] == f"eq.{NOTE}"
        else:
            assert request.url.params["disciplina_id"] == f"eq.{DISCIPLINE}"
            assert request.url.params["evento_id"] == f"eq.{EVENT}"
        return httpx.Response(200, json=[row(discipline=DISCIPLINE, event=EVENT)])

    client = simulated(handler)
    query = {"disciplina_id": str(DISCIPLINE), "evento_id": str(EVENT)}
    assert client.get("/anotacoes", params=query).status_code == 200
    assert client.get(f"/anotacoes/{NOTE}").json()["id"] == str(NOTE)


@pytest.mark.parametrize("discipline,event,body", [
    (None, None, "Texto"), (DISCIPLINE, None, "Texto"),
    (None, EVENT, "Texto"), (DISCIPLINE, EVENT, "Texto"),
    (None, None, ""),
])
def test_create_links_independent_and_empty_body(simulated, discipline, event, body):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append(request.url.path)
        if request.method == "GET":
            expected_id = DISCIPLINE if request.url.path.endswith("/disciplina") else EVENT
            assert request.url.params["id"] == f"eq.{expected_id}"
            assert request.url.params["usuario_id"] == f"eq.{USER}"
            return httpx.Response(200, json=[{"id": str(expected_id), "usuario_id": str(USER)}])
        assert request.method == "POST" and request.url.path == "/rest/v1/anotacao"
        assert request.url.params["select"] == SELECT
        data = json.loads(request.content)
        assert data == {"disciplina_id": str(discipline) if discipline else None,
                        "evento_id": str(event) if event else None,
                        "titulo": "Resumo", "corpo": body, "usuario_id": str(USER)}
        return httpx.Response(201, json=[row(discipline=discipline, event=event, body=body)])

    data = {"titulo": " Resumo ", "corpo": body}
    if discipline:
        data["disciplina_id"] = str(discipline)
    if event:
        data["evento_id"] = str(event)
    response = simulated(handler).post("/anotacoes", json=data)
    assert response.status_code == 201
    expected = (["/rest/v1/disciplina"] if discipline else []) + (["/rest/v1/evento"] if event else [])
    assert calls == expected + ["/rest/v1/anotacao"]


@pytest.mark.parametrize("data", [
    {"titulo": "Resumo"}, {"titulo": "Resumo", "corpo": None},
    {"titulo": " ", "corpo": "Texto"},
    {"titulo": "Resumo", "corpo": "Texto", "id": str(NOTE)},
    {"titulo": "Resumo", "corpo": "Texto", "usuario_id": str(USER)},
    {"titulo": "Resumo", "corpo": "Texto", "busca": "texto"},
    {"titulo": "Resumo", "corpo": "Texto", "criado_em": "2026-01-01T00:00:00Z"},
    {"titulo": "Resumo", "corpo": "Texto", "atualizado_em": "2026-01-01T00:00:00Z"},
    {"titulo": "Resumo", "corpo": "Texto", "disciplina_id": "bad"},
    {"titulo": "Resumo", "corpo": "Texto", "evento_id": "bad"},
])
def test_invalid_create(simulated, data):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.post("/anotacoes", json=data).status_code == 422


@pytest.mark.parametrize("data", [{}, {"titulo": None}, {"titulo": "  "},
                                    {"corpo": None}, {"id": str(NOTE)},
                                    {"usuario_id": str(USER)}, {"busca": "texto"},
                                    {"criado_em": "2026-01-01T00:00:00Z"},
                                    {"atualizado_em": "2026-01-01T00:00:00Z"}])
def test_invalid_patch(simulated, data):
    client = simulated(lambda request: pytest.fail("Unexpected HTTP request"))
    assert client.patch(f"/anotacoes/{NOTE}", json=data).status_code == 422


def test_patch_body_and_clear_links(simulated):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append(request.method)
        assert request.url.path == "/rest/v1/anotacao"
        assert request.url.params["id"] == f"eq.{NOTE}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        if request.method == "PATCH":
            assert json.loads(request.content) == {"disciplina_id": None, "evento_id": None,
                                                   "corpo": ""}
        return httpx.Response(200, json=[row(body="")])

    data = {"disciplina_id": None, "evento_id": None, "corpo": ""}
    assert simulated(handler).patch(f"/anotacoes/{NOTE}", json=data).status_code == 200
    assert calls == ["GET", "PATCH"]


def test_patch_reference(simulated):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/evento"):
            assert request.url.params["id"] == f"eq.{EVENT}"
            return httpx.Response(200, json=[{"id": str(EVENT), "usuario_id": str(USER)}])
        if request.method == "PATCH":
            assert json.loads(request.content) == {"evento_id": str(EVENT)}
        return httpx.Response(200, json=[row(event=EVENT)])

    assert simulated(handler).patch(f"/anotacoes/{NOTE}", json={"evento_id": str(EVENT)}).status_code == 200
    assert calls == [("GET", "/rest/v1/anotacao"), ("GET", "/rest/v1/evento"),
                     ("PATCH", "/rest/v1/anotacao")]


@pytest.mark.parametrize("table", ["disciplina", "evento"])
@pytest.mark.parametrize("owner", [None, OTHER])
def test_missing_or_foreign_reference(simulated, table, owner):
    def handler(request):
        if request.url.path == f"/rest/v1/{table}":
            rows = [] if owner is None else [{"id": str(DISCIPLINE if table == "disciplina" else EVENT),
                                              "usuario_id": str(owner)}]
            return httpx.Response(200, json=rows)
        pytest.fail("Unexpected write")

    data = {"titulo": "Resumo", "corpo": "Texto", f"{table}_id": str(DISCIPLINE if table == "disciplina" else EVENT)}
    assert simulated(handler).post("/anotacoes", json=data).status_code == 404


def test_delete(simulated):
    calls = []

    def handler(request):
        check_headers(request)
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        calls.append((request.method, request.url.path))
        if request.url.path == "/rest/v1/anexo":
            assert request.method == "GET"
            assert request.url.params["anotacao_id"] == f"eq.{NOTE}"
            assert request.url.params["limit"] == "1"
            return httpx.Response(200, json=[])
        assert request.url.params["id"] == f"eq.{NOTE}"
        return httpx.Response(200, json=[row()])

    assert simulated(handler).delete(f"/anotacoes/{NOTE}").status_code == 204
    assert calls == [("GET", "/rest/v1/anotacao"), ("GET", "/rest/v1/anexo"),
                     ("DELETE", "/rest/v1/anotacao")]


def test_delete_with_attachment_is_blocked(simulated):
    calls = []

    def handler(request):
        check_headers(request)
        calls.append((request.method, request.url.path))
        if request.url.path == "/rest/v1/anotacao":
            assert request.method == "GET"
            return httpx.Response(200, json=[row()])
        assert request.url.path == "/rest/v1/anexo" and request.method == "GET"
        assert request.url.params["anotacao_id"] == f"eq.{NOTE}"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        return httpx.Response(200, json=[{"id": str(NOTE)}])

    response = simulated(handler).delete(f"/anotacoes/{NOTE}")
    assert response.status_code == 409
    assert response.json()["detail"] == "Remova os anexos antes de excluir a anotação"
    assert calls == [("GET", "/rest/v1/anotacao"), ("GET", "/rest/v1/anexo")]


def test_delete_fails_closed_when_attachment_lookup_fails(simulated):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/rest/v1/anotacao":
            return httpx.Response(200, json=[row()])
        assert request.url.path == "/rest/v1/anexo" and request.method == "GET"
        return httpx.Response(503, json={"message": "private detail"})

    response = simulated(handler).delete(f"/anotacoes/{NOTE}")
    assert response.status_code == 503
    assert "private detail" not in response.text
    assert calls == [("GET", "/rest/v1/anotacao"), ("GET", "/rest/v1/anexo")]


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_inaccessible_note(simulated, method):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    response = client.request(method, f"/anotacoes/{NOTE}",
                              json={"corpo": "Outro"} if method == "PATCH" else None)
    assert response.status_code == 404


def test_foreign_row_rejected(simulated):
    assert simulated(lambda request: httpx.Response(200, json=[row(OTHER)])).get(
        "/anotacoes").status_code == 503


@pytest.mark.parametrize("status,body,expected", [
    (401, {}, 401), (403, {}, 403),
    (400, {"code": "23503", "message": "private detail"}, 422),
    (500, {"message": "private detail"}, 503),
])
def test_postgrest_errors(simulated, status, body, expected):
    response = simulated(lambda request: httpx.Response(status, json=body)).get("/anotacoes")
    assert response.status_code == expected
    assert "private detail" not in response.text


def test_network_failure(simulated):
    def handler(request):
        raise httpx.ConnectError("private network detail")

    response = simulated(handler).get("/anotacoes")
    assert response.status_code == 503
    assert "private network detail" not in response.text
