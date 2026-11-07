import socket

import pytest

from app.core.security import get_jwks_client


@pytest.fixture(autouse=True)
def offline_tests(monkeypatch):
    get_jwks_client.cache_clear()

    def forbidden(*args, **kwargs):
        raise AssertionError('Rede externa proibida nos testes unitários.')

    monkeypatch.setattr(socket, 'create_connection', forbidden)
    original_connect = socket.socket.connect

    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
            return original_connect(sock, address)
        return forbidden()

    monkeypatch.setattr(socket.socket, 'connect', local_only)
    yield
    get_jwks_client.cache_clear()
