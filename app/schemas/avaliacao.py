from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _clean_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Nome obrigatório")
    return value


class AvaliacaoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID
    nome: str
    peso: Decimal = Field(default=Decimal("1"), gt=Decimal("0"), allow_inf_nan=False)
    nota: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("10"), allow_inf_nan=False)
    data_prevista: date | None = None

    @model_validator(mode="after")
    def check(self):
        self.nome = _clean_name(self.nome)
        return self


class AvaliacaoPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID | None = None
    nome: str | None = None
    peso: Decimal | None = Field(default=None, gt=Decimal("0"), allow_inf_nan=False)
    nota: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("10"), allow_inf_nan=False)
    data_prevista: date | None = None

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set:
            raise ValueError("Alteração vazia")
        if any(getattr(self, field) is None for field in self.model_fields_set
               if field not in ("nota", "data_prevista")):
            raise ValueError("Campo obrigatório")
        if self.nome is not None:
            self.nome = _clean_name(self.nome)
        return self


class AvaliacaoOut(BaseModel):
    id: UUID
    usuario_id: UUID
    disciplina_id: UUID
    nome: str
    peso: Decimal
    nota: Decimal | None = None
    data_prevista: date | None = None
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
