from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AnexoOut(BaseModel):
    id: UUID
    usuario_id: UUID
    anotacao_id: UUID
    nome_arquivo: str
    caminho_storage: str
    tamanho_bytes: int
    tipo_mime: str
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None


class AnexoPublic(BaseModel):
    id: UUID
    anotacao_id: UUID
    nome_arquivo: str
    tamanho_bytes: int
    tipo_mime: str
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
