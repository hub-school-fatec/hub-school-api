from datetime import time
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies.identity import AuthenticatedIdentity
from app.repositories.supabase import PostgrestClient
from app.schemas.horario_aula import HorarioAulaOut


class HorarioAulaRepository:
    def __init__(self, client: PostgrestClient, discipline_client: PostgrestClient,
                 identity: AuthenticatedIdentity):
        self.client = client
        self.discipline_client = discipline_client
        self.identity = identity

    def _params(self, schedule_id: UUID) -> dict:
        return {"select": "*", "id": f"eq.{schedule_id}",
                "usuario_id": f"eq.{self.identity.user_id}"}

    def _rows(self, method: str, params: dict, data: dict | None = None) -> list[HorarioAulaOut]:
        raw = self.client.request(method, self.identity.access_token, params, data)
        try:
            rows = [HorarioAulaOut.model_validate(item) for item in raw]
        except ValidationError:
            raise HTTPException(503, "Serviço indisponível") from None
        if any(row.usuario_id != self.identity.user_id for row in rows):
            raise HTTPException(503, "Serviço indisponível")
        return rows

    @staticmethod
    def _one(rows: list[HorarioAulaOut]) -> HorarioAulaOut:
        if not rows:
            raise HTTPException(404, "Horário de aula não encontrado")
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

    def list(self, disciplina_id: UUID | None = None, dia_semana: int | None = None) -> list[HorarioAulaOut]:
        params = {"select": "*", "usuario_id": f"eq.{self.identity.user_id}"}
        if disciplina_id is not None:
            params["disciplina_id"] = f"eq.{disciplina_id}"
        if dia_semana is not None:
            params["dia_semana"] = f"eq.{dia_semana}"
        return self._rows("GET", params)

    def get(self, schedule_id: UUID) -> HorarioAulaOut:
        return self._one(self._rows("GET", self._params(schedule_id)))

    def create(self, data: dict) -> HorarioAulaOut:
        self._check_discipline(UUID(data["disciplina_id"]))
        rows = self._rows("POST", {"select": "*"},
                          {**data, "usuario_id": str(self.identity.user_id)})
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def patch(self, schedule_id: UUID, data: dict) -> HorarioAulaOut:
        current = self.get(schedule_id)
        if "disciplina_id" in data:
            self._check_discipline(UUID(data["disciplina_id"]))
        start = time.fromisoformat(data["hora_inicio"]) if "hora_inicio" in data else current.hora_inicio
        end = time.fromisoformat(data["hora_fim"]) if "hora_fim" in data else current.hora_fim
        if end <= start:
            raise HTTPException(422, "Intervalo de horário inválido")
        return self._one(self._rows("PATCH", self._params(schedule_id), data))

    def delete(self, schedule_id: UUID) -> None:
        self._one(self._rows("DELETE", self._params(schedule_id)))
