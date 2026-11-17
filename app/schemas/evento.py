from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator


TipoEvento = Literal["prova", "trabalho", "apresentacao", "aula", "evento"]
Antecedencia = Annotated[StrictInt, Field(ge=0)]


def _aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("Timezone obrigatório")
    return value


def _check_state(tipo: TipoEvento, horario_aula_id: UUID | None, data_aula: date | None,
                 inicio: datetime, fim: datetime | None) -> None:
    if fim is not None and fim < inicio:
        raise ValueError("Fim anterior ao início")
    if horario_aula_id is not None and (data_aula is None or tipo != "aula"):
        raise ValueError("Horário exige data_aula e tipo aula")


class EventoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID | None = None
    horario_aula_id: UUID | None = None
    data_aula: date | None = None
    tipo: TipoEvento
    titulo: str
    descricao: str | None = None
    inicio: datetime
    fim: datetime | None = None
    sala: str | None = None
    cancelado: StrictBool
    lembrete_ativo: StrictBool
    antecedencias_minutos: list[Antecedencia]

    @field_validator("inicio", "fim")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        return _aware(value) if value is not None else None

    @model_validator(mode="after")
    def check(self):
        self.titulo = self.titulo.strip()
        if not self.titulo:
            raise ValueError("Título obrigatório")
        _check_state(self.tipo, self.horario_aula_id, self.data_aula, self.inicio, self.fim)
        return self


class EventoPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID | None = None
    horario_aula_id: UUID | None = None
    data_aula: date | None = None
    tipo: TipoEvento | None = None
    titulo: str | None = None
    descricao: str | None = None
    inicio: datetime | None = None
    fim: datetime | None = None
    sala: str | None = None
    cancelado: StrictBool | None = None
    lembrete_ativo: StrictBool | None = None
    antecedencias_minutos: list[Antecedencia] | None = None

    @field_validator("inicio", "fim")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        return _aware(value) if value is not None else None

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set:
            raise ValueError("Alteração vazia")
        required = {"tipo", "titulo", "inicio", "cancelado", "lembrete_ativo", "antecedencias_minutos"}
        if any(getattr(self, field) is None for field in self.model_fields_set & required):
            raise ValueError("Campo obrigatório")
        if self.titulo is not None:
            self.titulo = self.titulo.strip()
            if not self.titulo:
                raise ValueError("Título obrigatório")
        return self


class EventoOut(BaseModel):
    id: UUID
    usuario_id: UUID
    disciplina_id: UUID | None = None
    horario_aula_id: UUID | None = None
    data_aula: date | None = None
    tipo: TipoEvento
    titulo: str
    descricao: str | None = None
    inicio: datetime
    fim: datetime | None = None
    sala: str | None = None
    cancelado: bool
    lembrete_ativo: bool
    antecedencias_minutos: list[int]
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
