from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies.identity import AuthenticatedIdentity
from app.repositories.supabase import PostgrestClient
from app.schemas.disciplina import DisciplinaOut


class DisciplinaRepository:
    def __init__(self, client: PostgrestClient, semester_client: PostgrestClient,
                 teacher_client: PostgrestClient, identity: AuthenticatedIdentity):
        self.client = client
        self.semester_client = semester_client
        self.teacher_client = teacher_client
        self.identity = identity

    def _params(self, discipline_id: UUID) -> dict:
        return {"select": "*", "id": f"eq.{discipline_id}",
                "usuario_id": f"eq.{self.identity.user_id}"}

    def _rows(self, method: str, params: dict, data: dict | None = None) -> list[DisciplinaOut]:
        raw = self.client.request(method, self.identity.access_token, params, data)
        try:
            rows = [DisciplinaOut.model_validate(item) for item in raw]
        except ValidationError:
            raise HTTPException(503, "Serviço indisponível") from None
        if any(row.usuario_id != self.identity.user_id for row in rows):
            raise HTTPException(503, "Serviço indisponível")
        return rows

    @staticmethod
    def _one(rows: list[DisciplinaOut]) -> DisciplinaOut:
        if not rows:
            raise HTTPException(404, "Disciplina não encontrada")
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
        if "semestre_id" in data:
            self._check_reference(self.semester_client, UUID(data["semestre_id"]))
        if data.get("docente_id") is not None:
            self._check_reference(self.teacher_client, UUID(data["docente_id"]))

    def list(self, semestre_id: UUID | None = None, docente_id: UUID | None = None) -> list[DisciplinaOut]:
        params = {"select": "*", "usuario_id": f"eq.{self.identity.user_id}"}
        if semestre_id is not None:
            params["semestre_id"] = f"eq.{semestre_id}"
        if docente_id is not None:
            params["docente_id"] = f"eq.{docente_id}"
        return self._rows("GET", params)

    def get(self, discipline_id: UUID) -> DisciplinaOut:
        return self._one(self._rows("GET", self._params(discipline_id)))

    def create(self, data: dict) -> DisciplinaOut:
        self._check_references(data)
        rows = self._rows("POST", {"select": "*"},
                          {**data, "usuario_id": str(self.identity.user_id)})
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def patch(self, discipline_id: UUID, data: dict) -> DisciplinaOut:
        # Evita verificar referencias para uma disciplina que o usuario nao possui.
        self.get(discipline_id)
        self._check_references(data)
        return self._one(self._rows("PATCH", self._params(discipline_id), data))

    def delete(self, discipline_id: UUID) -> None:
        self._one(self._rows("DELETE", self._params(discipline_id)))
