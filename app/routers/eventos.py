from datetime import datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.eventos import EventoRepository
from app.repositories.supabase import PostgrestClient
from app.routers.semestres import get_http_client
from app.schemas.evento import EventoCreate, EventoOut, EventoPatch, TipoEvento


router = APIRouter(prefix="/eventos", tags=["eventos"])


def get_repository(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    client: httpx.Client = Depends(get_http_client),
) -> EventoRepository:
    return EventoRepository(
        PostgrestClient(client, table="evento"),
        PostgrestClient(client, table="disciplina"),
        PostgrestClient(client, table="horario_aula"),
        identity,
    )


@router.get("", response_model=list[EventoOut])
def list_eventos(
    disciplina_id: UUID | None = None,
    tipo: TipoEvento | None = None,
    cancelado: bool | None = None,
    inicio: datetime | None = Query(default=None),
    fim: datetime | None = Query(default=None),
    repo: EventoRepository = Depends(get_repository),
):
    if any(value is not None and value.utcoffset() is None for value in (inicio, fim)):
        raise HTTPException(422, "Timezone obrigatório")
    if inicio is not None and fim is not None and fim < inicio:
        raise HTTPException(422, "Intervalo inválido")
    return repo.list(disciplina_id, tipo, cancelado, inicio, fim)


@router.get("/{event_id}", response_model=EventoOut)
def get_evento(event_id: UUID, repo: EventoRepository = Depends(get_repository)):
    return repo.get(event_id)


@router.post("", response_model=EventoOut, status_code=201)
def create_evento(body: EventoCreate, repo: EventoRepository = Depends(get_repository)):
    return repo.create(body.model_dump(mode="json"))


@router.patch("/{event_id}", response_model=EventoOut)
def patch_evento(event_id: UUID, body: EventoPatch,
                repo: EventoRepository = Depends(get_repository)):
    return repo.patch(event_id, body.model_dump(mode="json", exclude_unset=True))


@router.delete("/{event_id}", status_code=204)
def delete_evento(event_id: UUID, repo: EventoRepository = Depends(get_repository)):
    repo.delete(event_id)
    return Response(status_code=204)
