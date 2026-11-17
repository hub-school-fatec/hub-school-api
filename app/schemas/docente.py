import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


_EMAIL = re.compile(r"^[^@\s]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$")


def _clean_required(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{label} obrigatório")
    if label == "Email" and (len(value) > 254 or not _EMAIL.fullmatch(value)):
        raise ValueError("Email inválido")
    return value


class DocenteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str
    email: str
    telefone: str | None = None
    observacoes: str | None = None

    @model_validator(mode="after")
    def check(self):
        self.nome = _clean_required(self.nome, "Nome")
        self.email = _clean_required(self.email, "Email")
        return self


class DocentePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    observacoes: str | None = None

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set:
            raise ValueError("Alteração vazia")
        for field in ("nome", "email"):
            if field in self.model_fields_set:
                value = getattr(self, field)
                if value is None:
                    raise ValueError("Campo obrigatório")
                setattr(self, field, _clean_required(value, field.capitalize()))
        return self


class DocenteOut(BaseModel):
    id: UUID
    usuario_id: UUID
    nome: str
    email: str
    telefone: str | None = None
    observacoes: str | None = None
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
