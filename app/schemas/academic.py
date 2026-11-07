from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator


Text = Annotated[str, Field(min_length=1, max_length=500, pattern=r'.*\S.*')]
Identifier = Annotated[str, Field(min_length=1, max_length=200, pattern=r'^\S+$')]
NonNegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class SemesterInput(Contract):
    nome: Text
    data_inicio: date
    data_fim: date
    ativo: bool

    @model_validator(mode='after')
    def dates(self) -> Self:
        if self.data_fim < self.data_inicio:
            raise ValueError('Fim anterior ao início.')
        return self


class Semester(SemesterInput):
    id: Identifier


class TeacherInput(Contract):
    nome: Text
    email: Annotated[str, Field(max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')]
    telefone: Annotated[str, Field(max_length=100)] | None = None
    observacoes: Annotated[str, Field(max_length=20000)] = ''


class Teacher(TeacherInput):
    id: Identifier


class SubjectInput(Contract):
    semestre_id: Identifier
    docente_id: Identifier | None = None
    nome: Text
    sigla: Text
    total_aulas: Annotated[int, Field(gt=0, strict=True)]


class Subject(SubjectInput):
    id: Identifier


class ScheduleInput(Contract):
    disciplina_id: Identifier
    dia_semana: Annotated[int, Field(ge=0, le=6, strict=True, description='Segunda=0; domingo=6.')]
    hora_inicio: time
    hora_fim: time
    sala: Text

    @model_validator(mode='after')
    def times(self) -> Self:
        if self.hora_inicio.tzinfo or self.hora_fim.tzinfo:
            raise ValueError('Horários locais, sem offset.')
        if self.hora_fim <= self.hora_inicio:
            raise ValueError('Fim deve ser posterior ao início, no mesmo dia.')
        return self


class Schedule(ScheduleInput):
    id: Identifier


class AttendanceInput(Contract):
    disciplina_id: Identifier
    data: date
    aulas_no_dia: Annotated[int, Field(gt=0, strict=True)]
    faltas: Annotated[int, Field(ge=0, strict=True)]

    @model_validator(mode='after')
    def absences(self) -> Self:
        if self.faltas > self.aulas_no_dia:
            raise ValueError('Faltas maiores que aulas dadas.')
        return self


class Attendance(AttendanceInput):
    id: Identifier


class AssessmentInput(Contract):
    disciplina_id: Identifier
    nome: Text
    peso: Positive
    nota: NonNegative | None = None


class Assessment(AssessmentInput):
    id: Identifier


class EventInput(Contract):
    disciplina_id: Identifier | None = None
    tipo: Literal['prova', 'trabalho', 'apresentacao', 'aula', 'evento']
    titulo: Text
    inicio: AwareDatetime
    fim: AwareDatetime

    @model_validator(mode='after')
    def interval(self) -> Self:
        if self.fim <= self.inicio:
            raise ValueError('Fim deve ser posterior ao início.')
        return self


class Event(EventInput):
    id: Identifier


class NoteInput(Contract):
    disciplina_id: Identifier | None = None
    evento_id: Identifier | None = None
    titulo: Text
    corpo: Annotated[str, Field(max_length=100000)]


class Note(NoteInput):
    id: Identifier


class CalendarItem(Contract):
    id: Identifier
    data: date
    tipo: Literal['feriado', 'semana_provas', 'inicio', 'fim']
    descricao: Text


class AttendanceSummary(Contract):
    total_aulas: int
    aulas_dadas: int
    faltas: int
    presenca_percentual: Decimal | None
    faltas_percentual: Decimal | None
    limite_faltas: int
    faltas_restantes: int
    alerta: Literal['nenhum', 'acima_50', 'acima_80', 'limite_excedido']


class Average(Contract):
    media: Decimal | None
    avaliacoes_lancadas: int
    avaliacoes_pendentes: int


class Onboarding(Contract):
    semestres: list[Semester]
    disciplinas: list[Subject]
    horarios: list[Schedule]
    docentes: list[Teacher]


class Lesson(Contract):
    horario_id: Identifier
    disciplina_id: Identifier
    data: date
    hora_inicio: time
    hora_fim: time
    sala: Text


class Error(Contract):
    detail: str
