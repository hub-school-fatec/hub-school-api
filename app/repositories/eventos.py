from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies.identity import AuthenticatedIdentity
from app.repositories.supabase import PostgrestClient
from app.schemas.evento import EventoCreate, EventoOut, TipoEvento


_WRITABLE_FIELDS = {
    "disciplina_id", "horario_aula_id", "data_aula", "tipo", "titulo", "descricao",
    "inicio", "fim", "sala", "cancelado", "lembrete_ativo", "antecedencias_minutos",
}


class EventoRepository:
    def __init__(self, client: PostgrestClient, discipline_client: PostgrestClient,
                 schedule_client: PostgrestClient, identity: AuthenticatedIdentity):
        self.client = client
        self.discipline_client = discipline_client
        self.schedule_client = schedule_client
        self.identity = identity

    def _params(self, event_id: UUID) -> dict:
        return {"select": "*", "id": f"eq.{event_id}",
                "usuario_id": f"eq.{self.identity.user_id}"}

    def _rows(self, method: str, params: dict, data: dict | None = None) -> list[EventoOut]:
        raw = self.client.request(method, self.identity.access_token, params, data)
        try:
            rows = [EventoOut.model_validate(item) for item in raw]
        except ValidationError:
            raise HTTPException(503, "Serviço indisponível") from None
        if any(row.usuario_id != self.identity.user_id for row in rows):
            raise HTTPException(503, "Serviço indisponível")
        return rows

    @staticmethod
    def _one(rows: list[EventoOut]) -> EventoOut:
        if not rows:
            raise HTTPException(404, "Evento não encontrado")
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def _lookup(self, client: PostgrestClient, record_id: UUID, fields: str) -> dict:
        rows = client.request(
            "GET", self.identity.access_token,
            {"select": fields, "id": f"eq.{record_id}",
             "usuario_id": f"eq.{self.identity.user_id}"},
        )
        if not rows:
            raise HTTPException(404, "Referência não encontrada")
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        row = rows[0]
        try:
            if UUID(row["id"]) != record_id or UUID(row["usuario_id"]) != self.identity.user_id:
                raise HTTPException(404, "Referência não encontrada")
        except (KeyError, ValueError, TypeError):
            raise HTTPException(503, "Serviço indisponível") from None
        return row

    def _check_references(self, data: EventoCreate) -> None:
        if data.disciplina_id is not None:
            self._lookup(self.discipline_client, data.disciplina_id, "id,usuario_id")
        if data.horario_aula_id is not None:
            schedule = self._lookup(
                self.schedule_client, data.horario_aula_id, "id,usuario_id,disciplina_id",
            )
            try:
                schedule_discipline = UUID(schedule["disciplina_id"])
            except (KeyError, ValueError, TypeError):
                raise HTTPException(503, "Serviço indisponível") from None
            if data.disciplina_id is not None and schedule_discipline != data.disciplina_id:
                raise HTTPException(422, "Horário incompatível com a disciplina")

    def list(self, disciplina_id: UUID | None = None, tipo: TipoEvento | None = None,
             cancelado: bool | None = None, inicio: datetime | None = None,
             fim: datetime | None = None) -> list[EventoOut]:
        params = {"select": "*", "usuario_id": f"eq.{self.identity.user_id}"}
        if disciplina_id is not None:
            params["disciplina_id"] = f"eq.{disciplina_id}"
        if tipo is not None:
            params["tipo"] = f"eq.{tipo}"
        if cancelado is not None:
            params["cancelado"] = f"eq.{str(cancelado).lower()}"
        if inicio is not None:
            params["inicio"] = f"gte.{inicio.isoformat()}"
        if fim is not None:
            params["fim"] = f"lte.{fim.isoformat()}"
        return self._rows("GET", params)

    def get(self, event_id: UUID) -> EventoOut:
        return self._one(self._rows("GET", self._params(event_id)))

    def create(self, data: dict) -> EventoOut:
        event = EventoCreate.model_validate(data)
        self._check_references(event)
        rows = self._rows("POST", {"select": "*"},
                          {**data, "usuario_id": str(self.identity.user_id)})
        if len(rows) != 1:
            raise HTTPException(503, "Serviço indisponível")
        return rows[0]

    def patch(self, event_id: UUID, data: dict) -> EventoOut:
        current = self.get(event_id)
        merged = current.model_dump(mode="json", include=_WRITABLE_FIELDS)
        merged.update(data)
        try:
            final = EventoCreate.model_validate(merged)
        except ValidationError:
            raise HTTPException(422, "Evento inválido") from None
        self._check_references(final)
        return self._one(self._rows("PATCH", self._params(event_id), data))

    def delete(self, event_id: UUID) -> None:
        self._one(self._rows("DELETE", self._params(event_id)))
