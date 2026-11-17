from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


def _clean_title(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Título obrigatório")
    return value


class AnotacaoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID | None = None
    evento_id: UUID | None = None
    titulo: str
    corpo: str

    @model_validator(mode="after")
    def check(self):
        self.titulo = _clean_title(self.titulo)
        return self


class AnotacaoPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID | None = None
    evento_id: UUID | None = None
    titulo: str | None = None
    corpo: str | None = None

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set:
            raise ValueError("Alteração vazia")
        if "titulo" in self.model_fields_set:
            if self.titulo is None:
                raise ValueError("Título obrigatório")
            self.titulo = _clean_title(self.titulo)
        if "corpo" in self.model_fields_set and self.corpo is None:
            raise ValueError("Corpo obrigatório")
        return self


class AnotacaoOut(BaseModel):
    id: UUID
    usuario_id: UUID
    disciplina_id: UUID | None
    evento_id: UUID | None
    titulo: str
    corpo: str
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
