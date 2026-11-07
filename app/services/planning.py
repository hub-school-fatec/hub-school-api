from datetime import timedelta
from decimal import Decimal

from app.core.config import settings
from app.core.errors import DomainError
from app.schemas.planning import Calculation, CalculationInput, Reminder, ReminderInput, Situation, SituationInput
from app.services.academic import AcademicService


def calculate(payload: CalculationInput) -> Calculation:
    weight = sum((a.peso for a in payload.avaliacoes_lancadas), Decimal(0))
    points = sum((a.nota * a.peso for a in payload.avaliacoes_lancadas), Decimal(0))
    needed = max(Decimal(0), (settings.minimum_grade * (weight + payload.peso_proxima) - points) / payload.peso_proxima)
    maximum = (points + payload.nota_maxima * payload.peso_proxima) / (weight + payload.peso_proxima)
    return Calculation(nota_minima=needed, impossivel=needed > payload.nota_maxima,
                       media_maxima=maximum, media_alvo=settings.minimum_grade)


def situation(payload: SituationInput) -> Situation:
    criteria = []
    if (payload.presenca_percentual >= settings.minimum_attendance
            and payload.media is not None and payload.media >= settings.minimum_grade):
        criteria.append('aprovado')
    if (payload.faltas > Decimal(payload.limite_faltas) * Decimal('0.8')
            or payload.nota_minima_proxima is not None and payload.nota_minima_proxima > 8):
        criteria.append('em_risco')
    if (payload.faltas > payload.limite_faltas
            or payload.media_maxima_possivel is not None and payload.media_maxima_possivel < settings.minimum_grade):
        criteria.append('reprovado')
    return Situation(criterios_acionados=criteria,
                     situacao=criteria[0] if len(criteria) == 1 else None,
                     requer_definicao=len(criteria) != 1)


def reminders(service: AcademicService, event_id: str, payload: ReminderInput) -> list[Reminder]:
    event = service.get('eventos', event_id)
    if event['tipo'] not in {'prova', 'trabalho', 'apresentacao'}:
        raise DomainError(422, 'Lembretes previstos para provas, trabalhos e apresentações.')
    try:
        return [Reminder(evento_id=event_id, canal=payload.canal,
                         enviar_em=event['inicio'] - timedelta(days=days))
                for days in sorted(set(payload.antecedencia_dias), reverse=True)]
    except OverflowError:
        raise DomainError(422, 'Antecedência fora do intervalo de datas.') from None
