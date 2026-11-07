from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.dependencies.auth import get_current_user_id
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user_id] = lambda: 'A'
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.parametrize('grade,needed,impossible', [(8, 4, False), (0, 12, True), (10, 2, False)])
def test_calculator(client, grade, needed, impossible):
    response = client.post('/calculos/aprovacao', json={
        'avaliacoes_lancadas': [{'nota': grade, 'peso': 1}], 'peso_proxima': 1, 'nota_maxima': 10})
    assert response.status_code == 200
    assert Decimal(response.json()['nota_minima']) == needed
    assert response.json()['impossivel'] == impossible


def test_configurable_target_and_scale(client, monkeypatch):
    monkeypatch.setattr(settings, 'minimum_grade', Decimal(7))
    payload = {'avaliacoes_lancadas': [{'nota': 8, 'peso': 1}], 'peso_proxima': 1, 'nota_maxima': 10}
    assert Decimal(client.post('/calculos/aprovacao', json=payload).json()['nota_minima']) == 6
    payload['nota_maxima'] = 5
    assert client.post('/calculos/aprovacao', json=payload).status_code == 422
    payload['peso_proxima'] = 0
    assert client.post('/calculos/aprovacao', json=payload).status_code == 422


@pytest.mark.parametrize('changes,expected,ambiguous', [
    ({'media': 7}, ['aprovado'], False),
    ({'faltas': 17}, ['em_risco'], False),
    ({'media': 7, 'faltas': 17}, ['aprovado', 'em_risco'], True),
    ({'faltas': 21}, ['em_risco', 'reprovado'], True),
    ({'media_maxima_possivel': 5}, ['reprovado'], False),
    ({'nota_minima_proxima': 9}, ['em_risco'], False),
    ({}, [], True),
])
def test_situation_does_not_invent_precedence(client, changes, expected, ambiguous):
    payload = dict(presenca_percentual=80, faltas=0, limite_faltas=20)
    payload.update(changes)
    response = client.post('/calculos/situacao', json=payload)
    assert response.status_code == 200
    assert response.json()['criterios_acionados'] == expected
    assert response.json()['requer_definicao'] == ambiguous
    if ambiguous:
        assert response.json()['situacao'] is None
