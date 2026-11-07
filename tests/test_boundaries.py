from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.core.errors import DomainError
from app.schemas.planning import ReminderInput
from app.services.academic import AcademicService
from app.services.planning import reminders
from tests.fakes import MemoryRepository


@pytest.mark.parametrize('absences,alert,remaining', [
    (0, 'nenhum', 20), (10, 'nenhum', 10), (11, 'acima_50', 9),
    (16, 'acima_50', 4), (17, 'acima_80', 3), (20, 'acima_80', 0),
    (21, 'limite_excedido', 0),
])
def test_attendance_alert_boundaries(absences, alert, remaining):
    repo = MemoryRepository()
    subject = repo.create('disciplinas', {'total_aulas': 80}, 'A')
    repo.create('frequencias', {'disciplina_id': subject['id'], 'aulas_no_dia': 80,
                               'faltas': absences, 'data': date(2026, 1, 1)}, 'A')
    result = AcademicService(repo, 'A').attendance(subject['id'])
    assert result.alerta == alert
    assert result.faltas_restantes == remaining
    assert result.presenca_percentual + result.faltas_percentual == Decimal(100)


def test_reminder_duplicates_unsupported_type_and_foreign_event():
    repo = MemoryRepository()
    event = repo.create('eventos', {'tipo': 'prova', 'inicio': datetime(2026, 1, 10, tzinfo=timezone.utc)}, 'A')
    service = AcademicService(repo, 'A')
    result = reminders(service, event['id'], ReminderInput(antecedencia_dias=[1, 3, 3]))
    assert len(result) == 2
    assert result[0].enviar_em.day == 7
    with pytest.raises(DomainError) as exc:
        reminders(AcademicService(repo, 'B'), event['id'], ReminderInput())
    assert exc.value.status == 404
    repo.rows['eventos'][event['id']]['tipo'] = 'aula'
    with pytest.raises(DomainError) as exc:
        reminders(service, event['id'], ReminderInput())
    assert exc.value.status == 422


def test_note_with_attachment_is_not_deleted():
    repo = MemoryRepository()
    note = repo.create('anotacoes', {}, 'A')
    repo.create('anexos', {'anotacao_id': note['id']}, 'A')
    service = AcademicService(repo, 'A')
    with pytest.raises(DomainError) as exc:
        service.delete('anotacoes', note['id'])
    assert exc.value.status == 409
    assert service.get('anotacoes', note['id'])
