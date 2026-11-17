from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.main import app
from app.repositories import storage, supabase
from app.routers.semestres import get_http_client


USER = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")
NOTE = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
ATTACHMENT = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
FILE = b"%PDF-1.7\nexample"


def row(owner=USER, path=None, size=len(FILE)):
    return {"id": str(ATTACHMENT), "usuario_id": str(owner), "anotacao_id": str(NOTE),
            "nome_arquivo": "test.pdf", "caminho_storage": path or
            f"{owner}/{NOTE}/{ATTACHMENT}/test.pdf", "tamanho_bytes": size,
            "tipo_mime": "application/pdf"}


@pytest.fixture
def simulated(monkeypatch):
    settings = Settings(_env_file=None, supabase_url="https://test.supabase.co",
                        supabase_jwt_issuer="https://test.supabase.co/auth/v1",
                        supabase_publishable_key="sb_publishable_fake")
    monkeypatch.setattr(supabase, "get_settings", lambda: settings)
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
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
    assert TestClient(app).get("/anexos").status_code == 401


def test_list_get_and_owner_filter(simulated):
    def handler(request):
        check_headers(request)
        assert request.url.path == "/rest/v1/anexo"
        assert request.url.params["usuario_id"] == f"eq.{USER}"
        if "anotacao_id" in request.url.params:
            assert request.url.params["anotacao_id"] == f"eq.{NOTE}"
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    assert client.get("/anexos", params={"anotacao_id": str(NOTE)}).status_code == 200
    result = client.get(f"/anexos/{ATTACHMENT}")
    assert result.status_code == 200
    assert "caminho_storage" not in result.json()
    assert "usuario_id" not in result.json()


def test_empty_list_and_missing_record(simulated):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    assert client.get("/anexos").json() == []
    assert client.get(f"/anexos/{ATTACHMENT}").status_code == 404


def test_cross_user_response_rejected(simulated):
    client = simulated(lambda request: httpx.Response(200, json=[row(owner=OTHER)]))
    assert client.get(f"/anexos/{ATTACHMENT}").status_code == 503


def test_download_and_path_validation(simulated):
    def handler(request):
        check_headers(request)
        if request.url.path.startswith("/rest/v1/"):
            return httpx.Response(200, json=[row()])
        assert request.method == "GET"
        assert "/authenticated/hub-school-anexos/" in request.url.path
        return httpx.Response(200, content=FILE)

    client = simulated(handler)
    result = client.get(f"/anexos/{ATTACHMENT}/download")
    assert result.status_code == 200 and result.content == FILE
    assert result.headers["x-content-type-options"] == "nosniff"

    client = simulated(lambda request: httpx.Response(200, json=[row(path="other/path")]))
    assert client.get(f"/anexos/{ATTACHMENT}/download").status_code == 503


@pytest.mark.parametrize("payload,mime,filename", [
    (b"", "application/pdf", "test.pdf"),
    (b"hello", "application/pdf", "test.pdf"),
    (FILE, "text/plain", "test.pdf"),
    (FILE, "application/pdf", "../test.pdf"),
    (b"%PDF-" + b"x" * 10_485_760, "application/pdf", "test.pdf"),
])
def test_upload_rejects_invalid_files(simulated, payload, mime, filename):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path == "/rest/v1/anotacao"
        return httpx.Response(200, json=[{"id": str(NOTE), "usuario_id": str(USER)}])

    client = simulated(handler)
    result = client.post("/anexos/upload", data={"anotacao_id": str(NOTE)},
                         files={"arquivo": (filename, payload, mime)})
    assert result.status_code == 422
    assert all(request.method == "GET" for request in calls)


def test_upload_note_not_owned(simulated):
    client = simulated(lambda request: httpx.Response(200, json=[]))
    result = client.post("/anexos/upload", data={"anotacao_id": str(NOTE)},
                         files={"arquivo": ("test.pdf", FILE, "application/pdf")})
    assert result.status_code == 404


def test_upload_success_and_compensation(simulated):
    paths = []

    def handler(request):
        check_headers(request)
        paths.append((request.method, request.url.path))
        if request.url.path == "/rest/v1/anotacao":
            return httpx.Response(200, json=[{"id": str(NOTE), "usuario_id": str(USER)}])
        if request.method == "POST" and request.url.path.startswith("/storage/"):
            assert request.content == FILE
            assert request.headers["x-upsert"] == "false"
            return httpx.Response(200, json={})
        if request.url.path == "/rest/v1/anexo":
            import json
            body = json.loads(request.content)
            assert body["usuario_id"] == str(USER)
            return httpx.Response(201, json=[{**body}])
        raise AssertionError("unexpected request")

    client = simulated(handler)
    result = client.post("/anexos/upload", data={"anotacao_id": str(NOTE)},
                         files={"arquivo": ("test.pdf", FILE, "application/pdf")})
    assert result.status_code == 201
    assert [method for method, _ in paths] == ["GET", "POST", "POST"]


def test_metadata_failure_compensates(simulated):
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.url.path == "/rest/v1/anotacao":
            return httpx.Response(200, json=[{"id": str(NOTE), "usuario_id": str(USER)}])
        if request.url.path == "/rest/v1/anexo":
            return httpx.Response(409, json={})
        return httpx.Response(200, json={})

    client = simulated(handler)
    result = client.post("/anexos/upload", data={"anotacao_id": str(NOTE)},
                         files={"arquivo": ("test.pdf", FILE, "application/pdf")})
    assert result.status_code == 409
    assert methods == ["GET", "POST", "POST", "DELETE"]


def test_failed_compensation_reports_partial_state(simulated):
    def handler(request):
        if request.url.path == "/rest/v1/anotacao":
            return httpx.Response(200, json=[{"id": str(NOTE), "usuario_id": str(USER)}])
        if request.url.path == "/rest/v1/anexo":
            return httpx.Response(409, json={})
        if request.method == "DELETE":
            return httpx.Response(503)
        return httpx.Response(200, json={})

    client = simulated(handler)
    result = client.post("/anexos/upload", data={"anotacao_id": str(NOTE)},
                         files={"arquivo": ("test.pdf", FILE, "application/pdf")})
    assert result.status_code == 503
    assert "compensação" in result.text


def test_storage_failure_never_writes_metadata(simulated):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/rest/v1/anotacao":
            return httpx.Response(200, json=[{"id": str(NOTE), "usuario_id": str(USER)}])
        return httpx.Response(503)

    client = simulated(handler)
    result = client.post("/anexos/upload", data={"anotacao_id": str(NOTE)},
                         files={"arquivo": ("test.pdf", FILE, "application/pdf")})
    assert result.status_code == 503
    assert "/rest/v1/anexo" not in paths


def test_delete_and_partial_failure(simulated):
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=[row()])
        if request.url.path.startswith("/storage/"):
            return httpx.Response(204)
        return httpx.Response(200, json=[row()])

    client = simulated(handler)
    assert client.delete(f"/anexos/{ATTACHMENT}").status_code == 204
    assert methods == ["GET", "DELETE", "DELETE"]

    def partial(request):
        if request.method == "GET":
            return httpx.Response(200, json=[row()])
        if request.url.path.startswith("/storage/"):
            return httpx.Response(204)
        return httpx.Response(503)

    client = simulated(partial)
    assert client.delete(f"/anexos/{ATTACHMENT}").status_code == 503


def test_storage_delete_failure_preserves_metadata(simulated):
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=[row()])
        return httpx.Response(503)

    client = simulated(handler)
    assert client.delete(f"/anexos/{ATTACHMENT}").status_code == 503
    assert methods == ["GET", "DELETE"]


def test_invalid_stored_name_rejected(simulated):
    bad = row()
    bad["nome_arquivo"] = "../test.pdf"
    client = simulated(lambda request: httpx.Response(200, json=[bad]))
    assert client.get(f"/anexos/{ATTACHMENT}/download").status_code == 503


def test_network_failure_sanitized(simulated):
    def handler(request):
        raise httpx.ConnectError("private-token", request=request)

    client = simulated(handler)
    result = client.get("/anexos")
    assert result.status_code == 503
    assert "private-token" not in result.text
