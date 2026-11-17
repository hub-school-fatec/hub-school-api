from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies.identity import AuthenticatedIdentity
from app.repositories.supabase import PostgrestClient
from app.schemas.docente import DocenteOut


class DocenteRepository:
    def __init__(self, client: PostgrestClient, identity: AuthenticatedIdentity):
        self.client = client
        self.identity = identity

    def _rows(self, method: str, params: dict, data: dict | None = None) -> list[DocenteOut]:
        raw = self.client.request(method, self.identity.access_token, params, data)
        try:
            rows = [DocenteOut.model_validate(row) for row in raw]
        except ValidationError:
            raise HTTPException(503, "Serviço indisponível") from None
        if any(row.usuario_id != self.identity.user_id for row in rows):
            raise HTTPException(503, "Serviço indisponível")
        return rows

    def _params(self, teacher_id: UUID) -> dict:
        return {"select": "*", "id": f"eq.{teacher_id}",
                "usuario_id": f"eq.{self.identity.user_id}"}

    @staticmethod
    def _one(rows: list[DocenteOut]) -> DocenteOut:
        if not rows:
            raise HTTPException(404, "Docente não encontrado")
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def list(self) -> list[DocenteOut]:
        return self._rows("GET", {"select": "*", "usuario_id": f"eq.{self.identity.user_id}"})

    def get(self, teacher_id: UUID) -> DocenteOut:
        return self._one(self._rows("GET", self._params(teacher_id)))

    def create(self, data: dict) -> DocenteOut:
        rows = self._rows("POST", {"select": "*"}, {**data, "usuario_id": str(self.identity.user_id)})
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def patch(self, teacher_id: UUID, data: dict) -> DocenteOut:
        return self._one(self._rows("PATCH", self._params(teacher_id), data))

    def delete(self, teacher_id: UUID) -> None:
        self._one(self._rows("DELETE", self._params(teacher_id)))
