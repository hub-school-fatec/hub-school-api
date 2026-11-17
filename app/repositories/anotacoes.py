from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies.identity import AuthenticatedIdentity
from app.repositories.supabase import PostgrestClient
from app.schemas.anotacao import AnotacaoOut


_SELECT = "id,usuario_id,disciplina_id,evento_id,titulo,corpo,criado_em,atualizado_em"


class AnotacaoRepository:
    def __init__(self, client: PostgrestClient, discipline_client: PostgrestClient,
                 event_client: PostgrestClient, identity: AuthenticatedIdentity,
                 attachment_client: PostgrestClient):
        self.client = client
        self.discipline_client = discipline_client
        self.event_client = event_client
        self.identity = identity
        self.attachment_client = attachment_client

    def _params(self, note_id: UUID) -> dict:
        return {"select": _SELECT, "id": f"eq.{note_id}",
                "usuario_id": f"eq.{self.identity.user_id}"}

    def _rows(self, method: str, params: dict, data: dict | None = None) -> list[AnotacaoOut]:
        raw = self.client.request(method, self.identity.access_token, params, data)
        try:
            rows = [AnotacaoOut.model_validate(item) for item in raw]
        except ValidationError:
            raise HTTPException(503, "Serviço indisponível") from None
        if any(row.usuario_id != self.identity.user_id for row in rows):
            raise HTTPException(503, "Serviço indisponível")
        return rows

    @staticmethod
    def _one(rows: list[AnotacaoOut]) -> AnotacaoOut:
        if not rows:
            raise HTTPException(404, "Anotação não encontrada")
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def _check_reference(self, client: PostgrestClient, record_id: UUID) -> None:
        rows = client.request(
            "GET", self.identity.access_token,
            {"select": "id,usuario_id", "id": f"eq.{record_id}",
             "usuario_id": f"eq.{self.identity.user_id}"},
        )
        if not rows:
            raise HTTPException(404, "Referência não encontrada")
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        try:
            if UUID(rows[0]["id"]) != record_id or UUID(rows[0]["usuario_id"]) != self.identity.user_id:
                raise HTTPException(404, "Referência não encontrada")
        except (KeyError, ValueError, TypeError):
            raise HTTPException(503, "Serviço indisponível") from None

    def _check_references(self, data: dict) -> None:
        if data.get("disciplina_id") is not None:
            self._check_reference(self.discipline_client, UUID(data["disciplina_id"]))
        if data.get("evento_id") is not None:
            self._check_reference(self.event_client, UUID(data["evento_id"]))

    def list(self, disciplina_id: UUID | None = None, evento_id: UUID | None = None) -> list[AnotacaoOut]:
        params = {"select": _SELECT, "usuario_id": f"eq.{self.identity.user_id}"}
        if disciplina_id is not None:
            params["disciplina_id"] = f"eq.{disciplina_id}"
        if evento_id is not None:
            params["evento_id"] = f"eq.{evento_id}"
        return self._rows("GET", params)

    def get(self, note_id: UUID) -> AnotacaoOut:
        return self._one(self._rows("GET", self._params(note_id)))

    def create(self, data: dict) -> AnotacaoOut:
        self._check_references(data)
        rows = self._rows("POST", {"select": _SELECT},
                          {**data, "usuario_id": str(self.identity.user_id)})
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def patch(self, note_id: UUID, data: dict) -> AnotacaoOut:
        self.get(note_id)
        self._check_references(data)
        return self._one(self._rows("PATCH", self._params(note_id), data))

    def delete(self, note_id: UUID) -> None:
        self.get(note_id)
        # Consulta preventiva; um upload concorrente ainda pode ocorrer antes do DELETE.
        attachments = self.attachment_client.request(
            "GET", self.identity.access_token,
            {"select": "id", "anotacao_id": f"eq.{note_id}",
             "usuario_id": f"eq.{self.identity.user_id}", "limit": "1"},
        )
        if attachments:
            raise HTTPException(409, "Remova os anexos antes de excluir a anotação")
        self._one(self._rows("DELETE", self._params(note_id)))
