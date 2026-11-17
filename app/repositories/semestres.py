from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies.identity import AuthenticatedIdentity
from app.repositories.supabase import PostgrestClient
from app.schemas.semestre import SemestreOut


class SemestreRepository:
    def __init__(self, client: PostgrestClient, identity: AuthenticatedIdentity):
        self.client = client
        self.identity = identity

    def _rows(self, method: str, params: dict, data: dict | None = None) -> list[SemestreOut]:
        raw = self.client.request(method, self.identity.access_token, params, data)
        try:
            rows = [SemestreOut.model_validate(row) for row in raw]
        except ValidationError:
            raise HTTPException(503, "Serviço indisponível") from None
        if any(row.usuario_id != self.identity.user_id for row in rows):
            raise HTTPException(503, "Serviço indisponível")
        return rows

    def list(self) -> list[SemestreOut]:
        return self._rows("GET", {"select": "*", "usuario_id": f"eq.{self.identity.user_id}"})

    def get(self, semester_id: UUID) -> SemestreOut:
        rows = self._rows("GET", {"select": "*", "id": f"eq.{semester_id}",
                                   "usuario_id": f"eq.{self.identity.user_id}"})
        if len(rows) != 1:
            raise HTTPException(404 if not rows else 503, "Semestre não encontrado" if not rows else "Serviço indisponível")
        return rows[0]

    def create(self, data: dict) -> SemestreOut:
        rows = self._rows("POST", {"select": "*"}, {**data, "usuario_id": str(self.identity.user_id)})
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def patch(self, semester_id: UUID, data: dict) -> SemestreOut:
        rows = self._rows("PATCH", {"select": "*", "id": f"eq.{semester_id}",
                                     "usuario_id": f"eq.{self.identity.user_id}"}, data)
        if len(rows) != 1:
            raise HTTPException(404 if not rows else 503, "Semestre não encontrado" if not rows else "Serviço indisponível")
        return rows[0]

    def delete(self, semester_id: UUID) -> None:
        rows = self._rows("DELETE", {"select": "*", "id": f"eq.{semester_id}",
                                      "usuario_id": f"eq.{self.identity.user_id}"})
        if len(rows) != 1:
            raise HTTPException(404 if not rows else 503, "Semestre não encontrado" if not rows else "Serviço indisponível")
