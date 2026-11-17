from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies.identity import AuthenticatedIdentity
from app.repositories.supabase import PostgrestClient
from app.schemas.anexo import AnexoOut


_SELECT = "id,usuario_id,anotacao_id,nome_arquivo,caminho_storage,tamanho_bytes,tipo_mime,criado_em,atualizado_em"


class AnexoRepository:
    def __init__(self, client: PostgrestClient, note_client: PostgrestClient,
                 identity: AuthenticatedIdentity):
        self.client = client
        self.note_client = note_client
        self.identity = identity

    def _rows(self, method: str, params: dict, data: dict | None = None) -> list[AnexoOut]:
        raw = self.client.request(method, self.identity.access_token, params, data)
        try:
            rows = [AnexoOut.model_validate(item) for item in raw]
        except ValidationError:
            raise HTTPException(503, "Serviço indisponível") from None
        if any(row.usuario_id != self.identity.user_id for row in rows):
            raise HTTPException(503, "Serviço indisponível")
        return rows

    def note_exists(self, note_id: UUID) -> None:
        rows = self.note_client.request(
            "GET", self.identity.access_token,
            {"select": "id,usuario_id", "id": f"eq.{note_id}",
             "usuario_id": f"eq.{self.identity.user_id}"},
        )
        if not rows:
            raise HTTPException(404, "Anotação não encontrada")
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        try:
            if UUID(rows[0]["id"]) != note_id or UUID(rows[0]["usuario_id"]) != self.identity.user_id:
                raise HTTPException(404, "Anotação não encontrada")
        except (KeyError, ValueError, TypeError):
            raise HTTPException(503, "Serviço indisponível") from None

    def list(self, note_id: UUID | None = None) -> list[AnexoOut]:
        params = {"select": _SELECT, "usuario_id": f"eq.{self.identity.user_id}"}
        if note_id is not None:
            params["anotacao_id"] = f"eq.{note_id}"
        return self._rows("GET", params)

    def get(self, attachment_id: UUID) -> AnexoOut:
        rows = self._rows("GET", {"select": _SELECT, "id": f"eq.{attachment_id}",
                                  "usuario_id": f"eq.{self.identity.user_id}"})
        if not rows:
            raise HTTPException(404, "Anexo não encontrado")
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def create(self, data: dict) -> AnexoOut:
        rows = self._rows("POST", {"select": _SELECT},
                          {**data, "usuario_id": str(self.identity.user_id)})
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def delete(self, attachment_id: UUID) -> None:
        rows = self._rows("DELETE", {"select": _SELECT, "id": f"eq.{attachment_id}",
                                     "usuario_id": f"eq.{self.identity.user_id}"})
        if len(rows) != 1:
            raise HTTPException(404 if not rows else 503,
                                "Anexo não encontrado" if not rows else "Serviço indisponível")
