from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


def _nonempty(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Campo obrigatório")
    return value


class DisciplinaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semestre_id: UUID
    docente_id: UUID | None = None
    nome: str
    sigla: str
    carga_horaria_h: Decimal = Field(gt=Decimal("0"), allow_inf_nan=False)
    total_aulas: StrictInt = Field(gt=0)
    frequencia_minima: Decimal = Field(default=Decimal("75"), ge=0, le=100, allow_inf_nan=False)
    media_minima: Decimal = Field(default=Decimal("6"), ge=0, le=10, allow_inf_nan=False)

    @model_validator(mode="after")
    def check(self):
        self.nome = _nonempty(self.nome)
        self.sigla = _nonempty(self.sigla)
        return self


class DisciplinaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semestre_id: UUID | None = None
    docente_id: UUID | None = None
    nome: str | None = None
    sigla: str | None = None
    carga_horaria_h: Decimal | None = Field(default=None, gt=Decimal("0"), allow_inf_nan=False)
    total_aulas: StrictInt | None = Field(default=None, gt=0)
    frequencia_minima: Decimal | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    media_minima: Decimal | None = Field(default=None, ge=0, le=10, allow_inf_nan=False)

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set:
            raise ValueError("Alteração vazia")
        for field in self.model_fields_set:
            value = getattr(self, field)
            if value is None and field != "docente_id":
                raise ValueError("Campo obrigatório")
            if field in ("nome", "sigla") and value is not None:
                setattr(self, field, _nonempty(value))
        return self


class DisciplinaOut(BaseModel):
    id: UUID
    usuario_id: UUID
    semestre_id: UUID
    docente_id: UUID | None
    nome: str
    sigla: str
    carga_horaria_h: Decimal
    total_aulas: int
    frequencia_minima: Decimal
    media_minima: Decimal
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
