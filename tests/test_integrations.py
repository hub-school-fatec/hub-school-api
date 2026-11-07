import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.dependencies.auth import get_current_user_id
from app.integrations.contracts import get_attachment_gateway
from app.main import app
from app.repositories.base import get_repository
from app.schemas.planning import Attachment
from tests.fakes import MemoryRepository


def test_attachment_contract_ownership_and_stream_limit(monkeypatch):
    repo = MemoryRepository()
    note = repo.create('anotacoes', dict(titulo='N', corpo='', disciplina_id=None, evento_id=None), 'A')
    identity = {'id': 'A'}
    uploaded = []

    class Storage:
        def upload(self, user, note_id, name, stream):
            content = stream.read()
            uploaded.append((user, note_id, content))
            return Attachment(id='file', anotacao_id=note_id, nome_arquivo=name, tamanho_bytes=len(content))

        def list(self, user, note_id):
            return [Attachment(id='file', anotacao_id=note_id, nome_arquivo='a.pdf', tamanho_bytes=8)]

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_current_user_id] = lambda: identity['id']
    app.dependency_overrides[get_attachment_gateway] = Storage
    try:
        with TestClient(app) as client:
            path = f'/anotacoes/{note["id"]}/anexos'
            response = client.post(path, params={'nome_arquivo': 'a.pdf'}, content=b'%PDF-1.7')
            assert response.status_code == 201
            assert uploaded == [('A', note['id'], b'%PDF-1.7')]
            assert client.get(path).status_code == 200
            identity['id'] = 'B'
            assert client.get(path).status_code == 404
            assert client.post(path, params={'nome_arquivo': 'a.pdf'}, content=b'%PDF-1.7').status_code == 404
            identity['id'] = 'A'
            monkeypatch.setattr(settings, 'attachment_max_bytes', 5)
            assert client.post(path, params={'nome_arquivo': 'a.pdf'}, content=b'%PDF-1.7').status_code == 413
            assert len(uploaded) == 1
    finally:
        app.dependency_overrides.clear()


def test_openapi_security_and_unique_operations():
    spec = app.openapi()
    operations = []
    for path, methods in spec['paths'].items():
        for method, operation in methods.items():
            if method not in {'get', 'post', 'put', 'delete'}:
                continue
            operations.append(operation['operationId'])
            if path != '/health':
                assert operation['security'], (path, method)
            assert operation['responses']
    assert len(operations) == len(set(operations))


def test_every_private_route_requires_authentication():
    with TestClient(app) as client:
        for path, methods in app.openapi()['paths'].items():
            if path == '/health':
                continue
            for method in methods:
                if method in {'get', 'post', 'put', 'delete'}:
                    url = path.replace('{record_id}', 'missing').replace('{note_id}', 'missing').replace('{event_id}', 'missing')
                    response = client.request(method, url)
                    assert response.status_code == 401, (method, path, response.text)
