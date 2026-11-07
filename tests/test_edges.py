from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import DomainError
from app.dependencies.auth import get_current_user_id
from app.main import app
from app.repositories.base import get_repository
from app.schemas.academic import SemesterInput, SubjectInput
from app.services.academic import AcademicService
from app.services.attachments import validate_attachment
from tests.fakes import MemoryRepository


def test_empty_metrics_and_rounding(monkeypatch):
    service = AcademicService(MemoryRepository(), 'A')
    semester = service.save('semestres', SemesterInput(nome='S', data_inicio='2026-01-01', data_fim='2026-06-01', ativo=True))
    subject = service.save('disciplinas', SubjectInput(semestre_id=semester['id'], nome='D', sigla='D', total_aulas=7))
    summary = service.attendance(subject['id'])
    assert summary.presenca_percentual is None
    assert summary.faltas_percentual is None
    assert summary.limite_faltas == 1
    assert service.average(subject['id']).media is None
    monkeypatch.setattr(settings, 'minimum_attendance', Decimal(50))
    assert service.attendance(subject['id']).limite_faltas == 3


def test_atomic_semester_conflict_in_test_repository():
    service = AcademicService(MemoryRepository(), 'A')
    payload = SemesterInput(nome='S', data_inicio='2026-01-01', data_fim='2026-06-01', ativo=True)
    def save(_):
        try:
            service.save('semestres', payload)
            return 201
        except DomainError as exc:
            return exc.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == [201, 409]
    assert len(service.list('semestres')) == 1


@pytest.mark.parametrize('name,content', [('a.pdf', b'%PDF-1.7'), ('a.png', b'\x89PNG\r\n\x1a\n'),
                                        ('a.jpg', b'\xff\xd8\xff'), ('a.gif', b'GIF89a'),
                                        ('a.webp', b'RIFF1234WEBP')])
def test_attachment_signature_filter(name, content):
    validate_attachment(name, content)


@pytest.mark.parametrize('name,content,status', [('../a.pdf', b'%PDF-', 422), ('a.pdf', b'', 422),
                                               ('a.pdf', b'<script>', 415), ('a.svg', b'<svg>', 415)])
def test_attachment_rejections(name, content, status):
    with pytest.raises(DomainError) as exc:
        validate_attachment(name, content)
    assert exc.value.status == status


def test_attachment_size(monkeypatch):
    monkeypatch.setattr(settings, 'attachment_max_bytes', 5)
    with pytest.raises(DomainError) as exc:
        validate_attachment('a.pdf', b'%PDF-1234')
    assert exc.value.status == 413


def test_internal_error_redacted():
    class Broken(MemoryRepository):
        def list(self, *args):
            raise RuntimeError('secret database connection')
    app.dependency_overrides[get_repository] = lambda: Broken()
    app.dependency_overrides[get_current_user_id] = lambda: 'A'
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get('/semestres')
            assert response.status_code == 500
            assert response.json() == {'detail': 'Erro interno.'}
    finally:
        app.dependency_overrides.clear()
