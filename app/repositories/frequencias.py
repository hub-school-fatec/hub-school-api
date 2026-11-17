from datetime import date
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies.identity import AuthenticatedIdentity
from app.repositories.supabase import PostgrestClient
from app.schemas.frequencia import FrequenciaOut


class FrequenciaRepository:
    def __init__(self, client: PostgrestClient, discipline_client: PostgrestClient,
                 identity: AuthenticatedIdentity):
        self.client = client
        self.discipline_client = discipline_client
        self.identity = identity

    def _params(self, frequency_id: UUID) -> dict:
        return {"select": "*", "id": f"eq.{frequency_id}",
                "usuario_id": f"eq.{self.identity.user_id}"}

    def _rows(self, method: str, params: dict, data: dict | None = None) -> list[FrequenciaOut]:
        raw = self.client.request(method, self.identity.access_token, params, data)
        try:
            rows = [FrequenciaOut.model_validate(item) for item in raw]
        except ValidationError:
            raise HTTPException(503, "Serviço indisponível") from None
        if any(row.usuario_id != self.identity.user_id for row in rows):
            raise HTTPException(503, "Serviço indisponível")
        return rows

    @staticmethod
    def _one(rows: list[FrequenciaOut]) -> FrequenciaOut:
        if not rows:
            raise HTTPException(404, "Frequência não encontrada")
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def _check_discipline(self, discipline_id: UUID) -> None:
        rows = self.discipline_client.request(
            "GET", self.identity.access_token,
            {"select": "id,usuario_id", "id": f"eq.{discipline_id}",
             "usuario_id": f"eq.{self.identity.user_id}"},
        )
        if not rows:
            raise HTTPException(404, "Disciplina não encontrada")
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        try:
            if UUID(rows[0]["id"]) != discipline_id or UUID(rows[0]["usuario_id"]) != self.identity.user_id:
                raise HTTPException(404, "Disciplina não encontrada")
        except (KeyError, ValueError, TypeError):
            raise HTTPException(503, "Serviço indisponível") from None

    def list(self, disciplina_id: UUID | None = None, data: date | None = None) -> list[FrequenciaOut]:
        params = {"select": "*", "usuario_id": f"eq.{self.identity.user_id}"}
        if disciplina_id is not None:
            params["disciplina_id"] = f"eq.{disciplina_id}"
        if data is not None:
            params["data"] = f"eq.{data.isoformat()}"
        return self._rows("GET", params)

    def get(self, frequency_id: UUID) -> FrequenciaOut:
        return self._one(self._rows("GET", self._params(frequency_id)))

    def create(self, data: dict) -> FrequenciaOut:
        self._check_discipline(UUID(data["disciplina_id"]))
        rows = self._rows("POST", {"select": "*"},
                          {**data, "usuario_id": str(self.identity.user_id)})
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def patch(self, frequency_id: UUID, data: dict) -> FrequenciaOut:
        current = self.get(frequency_id)
        if "disciplina_id" in data:
            self._check_discipline(UUID(data["disciplina_id"]))
        aulas = data.get("aulas_no_dia", current.aulas_no_dia)
        faltas = data.get("faltas", current.faltas)
        if aulas <= 0 or faltas < 0 or faltas > aulas:
            raise HTTPException(422, "Faltas excedem aulas no dia")
        return self._one(self._rows("PATCH", self._params(frequency_id), data))

    def delete(self, frequency_id: UUID) -> None:
        self._one(self._rows("DELETE", self._params(frequency_id)))
