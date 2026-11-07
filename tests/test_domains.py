from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user_id
from app.main import app
from app.repositories.base import get_repository
from tests.fakes import MemoryRepository


@pytest.fixture
def api():
    repo = MemoryRepository()
    identity = {'id': 'A'}
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_current_user_id] = lambda: identity['id']
    with TestClient(app) as client:
        yield client, identity, repo
    app.dependency_overrides.clear()


def create(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def seed(client):
    semester = create(client, '/semestres', dict(nome='2026/2', data_inicio='2026-08-01', data_fim='2026-12-20', ativo=True))
    teacher = create(client, '/docentes', dict(nome='Docente', email='docente@example.org'))
    subject = create(client, '/disciplinas', dict(semestre_id=semester['id'], docente_id=teacher['id'], nome='Matemática', sigla='MAT', total_aulas=80))
    schedule = create(client, '/horarios', dict(disciplina_id=subject['id'], dia_semana=0, hora_inicio='19:00', hora_fim='20:00', sala='1'))
    attendance = create(client, '/frequencias', dict(disciplina_id=subject['id'], data='2026-09-07', aulas_no_dia=40, faltas=12))
    assessment = create(client, '/avaliacoes', dict(disciplina_id=subject['id'], nome='P1', peso=1, nota=8))
    event = create(client, '/eventos', dict(disciplina_id=subject['id'], tipo='prova', titulo='P1', inicio='2026-09-10T19:00:00-03:00', fim='2026-09-10T21:00:00-03:00'))
    note = create(client, '/anotacoes', dict(disciplina_id=subject['id'], evento_id=event['id'], titulo='Revisão', corpo='Integrais'))
    return dict(semestres=semester, docentes=teacher, disciplinas=subject, horarios=schedule,
                frequencias=attendance, avaliacoes=assessment, eventos=event, anotacoes=note)


@pytest.mark.parametrize('owner,other', [('A', 'B'), ('B', 'A')])
def test_all_resources_isolated(api, owner, other):
    client, identity, repo = api
    identity['id'] = owner
    own = seed(client)
    identity['id'] = other
    foreign = seed(client)
    identity['id'] = owner
    for entity in own:
        assert client.get(f'/{entity}/{own[entity]["id"]}').status_code == 200
        assert client.get(f'/{entity}').json() == [own[entity]]
        foreign_path = f'/{entity}/{foreign[entity]["id"]}'
        assert client.get(foreign_path).status_code == 404
        payload = {k: v for k, v in own[entity].items() if k != 'id'}
        assert client.put(foreign_path, json=payload).status_code == 404
        assert client.put(f'/{entity}/{own[entity]["id"]}', json=payload).status_code == 200
        assert client.get(f'/{entity}/missing').status_code == 404
        assert client.post(f'/{entity}', json=dict(payload, usuario_id=other)).status_code == 422
    for entity in ('docentes', 'anotacoes'):
        assert client.delete(f'/{entity}/{foreign[entity]["id"]}').status_code == 404


@pytest.mark.parametrize('owner,other', [('A', 'B'), ('B', 'A')])
def test_foreign_links_on_create_and_update(api, owner, other):
    client, identity, _ = api
    identity['id'] = owner
    own = seed(client)
    identity['id'] = other
    foreign = seed(client)
    identity['id'] = owner
    links = [('disciplinas', 'semestre_id', 'semestres'), ('disciplinas', 'docente_id', 'docentes'),
             ('horarios', 'disciplina_id', 'disciplinas'), ('frequencias', 'disciplina_id', 'disciplinas'),
             ('avaliacoes', 'disciplina_id', 'disciplinas'), ('eventos', 'disciplina_id', 'disciplinas'),
             ('anotacoes', 'disciplina_id', 'disciplinas'), ('anotacoes', 'evento_id', 'eventos')]
    for entity, field, target in links:
        payload = {k: v for k, v in own[entity].items() if k != 'id'}
        payload[field] = foreign[target]['id']
        assert client.post(f'/{entity}', json=payload).status_code == 404
        assert client.put(f'/{entity}/{own[entity]["id"]}', json=payload).status_code == 404


def test_rules_and_aggregate_endpoints(api):
    client, _, repo = api
    data = seed(client)
    subject = data['disciplinas']['id']
    summary = client.get(f'/disciplinas/{subject}/resumo-frequencia').json()
    assert summary['limite_faltas'] == 20
    assert summary['faltas_restantes'] == 8
    assert Decimal(summary['presenca_percentual']) == 70
    assert summary['alerta'] == 'acima_50'
    assert Decimal(client.get(f'/disciplinas/{subject}/media').json()['media']) == 8
    create(client, '/avaliacoes', dict(disciplina_id=subject, nome='P2', peso=3, nota=4))
    create(client, '/avaliacoes', dict(disciplina_id=subject, nome='Trabalho', peso=1, nota=None))
    mean = client.get(f'/disciplinas/{subject}/media').json()
    assert Decimal(mean['media']) == 5
    assert mean['avaliacoes_pendentes'] == 1
    semester_input = {k: v for k, v in data['semestres'].items() if k != 'id'}
    assert client.post('/semestres', json=semester_input).status_code == 409
    freq = {k: v for k, v in data['frequencias'].items() if k != 'id'}
    assert client.post('/frequencias', json=freq).status_code == 409
    assert client.delete(f'/docentes/{data["docentes"]["id"]}').status_code == 409
    assert client.delete(f'/anotacoes/{data["anotacoes"]["id"]}').status_code == 204
    assert client.delete(f'/anotacoes/{data["anotacoes"]["id"]}').status_code == 404
    assert len(client.get('/primeiro-acesso').json()['disciplinas']) == 1
    lessons = client.get('/aulas-recorrentes', params={'inicio': '2026-07-01', 'fim': '2026-08-10'}).json()
    assert [r['data'] for r in lessons] == ['2026-08-03', '2026-08-10']
    assert client.get('/aulas-recorrentes', params={'inicio': '2026-01-01', 'fim': '2028-01-01'}).status_code == 422
    repo.calendar_rows = [dict(id='global', data=date(2026, 9, 7), tipo='feriado', descricao='Feriado')]
    assert client.get('/calendario-academico').json()[0]['id'] == 'global'
    preview = client.post(f'/eventos/{data["eventos"]["id"]}/previa-lembretes', json={})
    assert preview.status_code == 200
    assert [r['enviar_em'][:10] for r in preview.json()] == ['2026-09-07', '2026-09-09']


def test_filters_pagination_and_validation(api):
    client, _, _ = api
    data = seed(client)
    assert client.get('/anotacoes', params={'texto': 'integrais'}).json() == [data['anotacoes']]
    assert client.get('/anotacoes', params={'texto': 'ausente'}).json() == []
    assert client.get('/disciplinas', params={'semestre_id': data['semestres']['id']}).json() == [data['disciplinas']]
    assert client.get('/docentes', params={'offset': 1}).json() == []
    assert client.get('/docentes', params={'limit': 101}).status_code == 422
    assert client.get('/eventos', params={'inicio': '2026-09-11T00:00:00Z'}).json() == []
    assert client.get('/eventos', params={'tipo': 'prova'}).json() == [data['eventos']]
    assert client.get('/eventos', params={'tipo': 'trabalho'}).json() == []
    assert client.get('/eventos', params={'tipo': 'invalido'}).status_code == 422
    for entity, changes in [
        ('semestres', {'data_fim': '2025-01-01'}), ('docentes', {'email': 'invalid'}),
        ('disciplinas', {'total_aulas': 0}), ('horarios', {'dia_semana': 7}),
        ('horarios', {'hora_fim': '18:00'}), ('frequencias', {'faltas': 41}),
        ('avaliacoes', {'peso': 0}), ('avaliacoes', {'nota': -1}),
        ('eventos', {'inicio': '2026-09-10T19:00:00'}), ('anotacoes', {'titulo': '  '}),
    ]:
        payload = {k: v for k, v in data[entity].items() if k != 'id'}
        payload.update(changes)
        response = client.post(f'/{entity}', json=payload)
        assert response.status_code == 422, (entity, response.text)
        assert 'input' not in response.text


def test_fail_closed_with_leaky_repository(api, monkeypatch):
    client, identity, repo = api
    other = seed(client)
    identity['id'] = 'B'
    foreign = repo.rows['semestres'][other['semestres']['id']]
    monkeypatch.setattr(repo, 'list', lambda *a: [foreign])
    monkeypatch.setattr(repo, 'get', lambda *a: foreign)
    assert client.get('/semestres').json() == []
    assert client.get(f'/semestres/{foreign["id"]}').status_code == 404


def test_unintegrated_and_protected():
    with TestClient(app) as client:
        assert client.get('/semestres').status_code == 401
        assert client.post('/calculos/aprovacao', json={}).status_code == 401
        app.dependency_overrides[get_current_user_id] = lambda: 'A'
        try:
            for path in ('/semestres', '/docentes', '/primeiro-acesso', '/conta/exportacao', '/calendario-academico'):
                assert client.get(path).status_code == 503
            assert client.request('DELETE', '/conta', json={'confirmar_exclusao': True}).status_code == 503
        finally:
            app.dependency_overrides.clear()
