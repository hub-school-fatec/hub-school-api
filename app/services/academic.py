from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR

from app.core.config import settings
from app.core.errors import DomainError
from app.repositories.base import Record, Repository
from app.schemas.academic import AttendanceSummary, Average, Contract, Lesson


LINKS = {
    'semestres': {}, 'docentes': {},
    'disciplinas': {'semestre_id': 'semestres', 'docente_id': 'docentes'},
    'horarios': {'disciplina_id': 'disciplinas'},
    'frequencias': {'disciplina_id': 'disciplinas'},
    'avaliacoes': {'disciplina_id': 'disciplinas'},
    'eventos': {'disciplina_id': 'disciplinas'},
    'anotacoes': {'disciplina_id': 'disciplinas', 'evento_id': 'eventos'},
    'anexos': {'anotacao_id': 'anotacoes'},
}


class AcademicService:
    def __init__(self, repo: Repository, user_id: str):
        self.repo = repo
        self.user_id = user_id

    def get(self, entity: str, record_id: str) -> Record:
        row = self.repo.get(entity, record_id, self.user_id)
        if row is None or row.get('usuario_id') != self.user_id:
            raise DomainError(404, 'Recurso não encontrado.')
        return row

    def list(self, entity: str) -> list[Record]:
        return [r for r in self.repo.list(entity, self.user_id)
                if r.get('usuario_id') == self.user_id]

    def save(self, entity: str, payload: Contract, record_id: str | None = None) -> Record:
        values = payload.model_dump()
        with self.repo.transaction(self.user_id):
            if record_id is not None:
                self.get(entity, record_id)
            for field, target in LINKS[entity].items():
                if values.get(field) is not None:
                    self.get(target, values[field])
            if entity == 'semestres' and values['ativo']:
                if any(r['ativo'] and r['id'] != record_id for r in self.list(entity)):
                    raise DomainError(409, 'Já existe um semestre ativo. Desative-o antes.')
            if entity == 'frequencias':
                if any(r['id'] != record_id and r['disciplina_id'] == values['disciplina_id']
                       and r['data'] == values['data'] for r in self.list(entity)):
                    raise DomainError(409, 'Frequência já registrada nesta data. Atualize o registro.')
            if record_id is None:
                result = self.repo.create(entity, values, self.user_id)
            else:
                result = self.repo.update(entity, record_id, values, self.user_id)
            if result.get('usuario_id') != self.user_id:
                raise DomainError(500, 'Resposta de persistência inválida.')
            return result

    def delete(self, entity: str, record_id: str) -> None:
        with self.repo.transaction(self.user_id):
            self.get(entity, record_id)
            for source, links in LINKS.items():
                for field, target in links.items():
                    if target == entity and any(r.get(field) == record_id for r in self.list(source)):
                        raise DomainError(409, 'Recurso possui vínculos; exclusão indisponível.')
            self.repo.delete(entity, record_id, self.user_id)

    def attendance(self, subject_id: str) -> AttendanceSummary:
        subject = self.get('disciplinas', subject_id)
        rows = [r for r in self.list('frequencias') if r['disciplina_id'] == subject_id]
        lessons = sum(r['aulas_no_dia'] for r in rows)
        absences = sum(r['faltas'] for r in rows)
        limit = int((Decimal(subject['total_aulas']) * (1 - settings.minimum_attendance / 100))
                    .to_integral_value(rounding=ROUND_FLOOR))
        alert = 'nenhum'
        if absences > limit:
            alert = 'limite_excedido'
        elif absences > Decimal(limit) * Decimal('0.8'):
            alert = 'acima_80'
        elif absences > Decimal(limit) * Decimal('0.5'):
            alert = 'acima_50'
        return AttendanceSummary(
            total_aulas=subject['total_aulas'], aulas_dadas=lessons, faltas=absences,
            presenca_percentual=Decimal(lessons - absences) * 100 / lessons if lessons else None,
            faltas_percentual=Decimal(absences) * 100 / lessons if lessons else None,
            limite_faltas=limit, faltas_restantes=max(0, limit - absences), alerta=alert,
        )

    def average(self, subject_id: str) -> Average:
        self.get('disciplinas', subject_id)
        rows = [r for r in self.list('avaliacoes') if r['disciplina_id'] == subject_id]
        graded = [r for r in rows if r['nota'] is not None]
        weights = sum((r['peso'] for r in graded), Decimal(0))
        mean = sum((r['nota'] * r['peso'] for r in graded), Decimal(0)) / weights if weights else None
        return Average(media=mean, avaliacoes_lancadas=len(graded),
                       avaliacoes_pendentes=len(rows) - len(graded))

    def lessons(self, start: date, end: date) -> list[Lesson]:
        if end < start or (end - start).days > 366:
            raise DomainError(422, 'Intervalo deve ter de 0 a 366 dias.')
        result = []
        for schedule in self.list('horarios'):
            subject = self.get('disciplinas', schedule['disciplina_id'])
            semester = self.get('semestres', subject['semestre_id'])
            current = max(start, semester['data_inicio'])
            last = min(end, semester['data_fim'])
            current += timedelta(days=(schedule['dia_semana'] - current.weekday()) % 7)
            while current <= last:
                result.append(Lesson(horario_id=schedule['id'], disciplina_id=subject['id'],
                                     data=current, hora_inicio=schedule['hora_inicio'],
                                     hora_fim=schedule['hora_fim'], sala=schedule['sala']))
                current += timedelta(days=7)
        return sorted(result, key=lambda r: (r.data, r.hora_inicio, r.horario_id))
