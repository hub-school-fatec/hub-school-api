from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class SemestreCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str = Field(min_length=1)
    data_inicio: date
    data_fim: date
    ativo: StrictBool = False

    @model_validator(mode="after")
    def check(self):
        self.nome = self.nome.strip()
        if not self.nome or self.data_fim < self.data_inicio:
            raise ValueError("Nome ou período inválido")
        return self


class SemestrePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    ativo: StrictBool | None = None

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Alteração inválida")
        if self.nome is not None:
            self.nome = self.nome.strip()
            if not self.nome:
                raise ValueError("Nome inválido")
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValueError("Período inválido")
        return self


class SemestreOut(BaseModel):
    id: UUID
    usuario_id: UUID
    nome: str
    data_inicio: date
    data_fim: date
    ativo: bool
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
