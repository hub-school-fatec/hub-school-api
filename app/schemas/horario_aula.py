from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


def _valid_room(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Sala obrigatória")
    return value


class HorarioAulaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID
    dia_semana: StrictInt = Field(ge=1, le=7)
    hora_inicio: time
    hora_fim: time
    sala: str
    aulas_no_dia: StrictInt = Field(default=1, gt=0)

    @field_validator("hora_inicio", "hora_fim")
    @classmethod
    def local_time(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("Hora sem fuso obrigatória")
        return value

    @model_validator(mode="after")
    def check(self):
        self.sala = _valid_room(self.sala)
        if self.hora_fim <= self.hora_inicio:
            raise ValueError("Intervalo de horário inválido")
        return self


class HorarioAulaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID | None = None
    dia_semana: StrictInt | None = Field(default=None, ge=1, le=7)
    hora_inicio: time | None = None
    hora_fim: time | None = None
    sala: str | None = None
    aulas_no_dia: StrictInt | None = Field(default=None, gt=0)

    @field_validator("hora_inicio", "hora_fim")
    @classmethod
    def local_time(cls, value: time | None) -> time | None:
        if value is not None and value.tzinfo is not None:
            raise ValueError("Hora sem fuso obrigatória")
        return value

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Alteração inválida")
        if self.sala is not None:
            self.sala = _valid_room(self.sala)
        if self.hora_inicio is not None and self.hora_fim is not None and self.hora_fim <= self.hora_inicio:
            raise ValueError("Intervalo de horário inválido")
        return self


class HorarioAulaOut(BaseModel):
    id: UUID
    usuario_id: UUID
    disciplina_id: UUID
    dia_semana: int
    hora_inicio: time
    hora_fim: time
    sala: str
    aulas_no_dia: int
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
