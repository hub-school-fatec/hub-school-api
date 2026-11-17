from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Query, Response

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.horarios_aula import HorarioAulaRepository
from app.repositories.supabase import PostgrestClient
from app.routers.semestres import get_http_client
from app.schemas.horario_aula import HorarioAulaCreate, HorarioAulaOut, HorarioAulaPatch


router = APIRouter(prefix="/horarios-aula", tags=["horarios-aula"])


def get_repository(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    client: httpx.Client = Depends(get_http_client),
) -> HorarioAulaRepository:
    return HorarioAulaRepository(
        PostgrestClient(client, table="horario_aula"),
        PostgrestClient(client, table="disciplina"),
        identity,
    )


@router.get("", response_model=list[HorarioAulaOut])
def list_horarios_aula(
    disciplina_id: UUID | None = None,
    dia_semana: int | None = Query(default=None, ge=1, le=7),
    repo: HorarioAulaRepository = Depends(get_repository),
):
    return repo.list(disciplina_id, dia_semana)


@router.get("/{schedule_id}", response_model=HorarioAulaOut)
def get_horario_aula(schedule_id: UUID, repo: HorarioAulaRepository = Depends(get_repository)):
    return repo.get(schedule_id)


@router.post("", response_model=HorarioAulaOut, status_code=201)
def create_horario_aula(body: HorarioAulaCreate, repo: HorarioAulaRepository = Depends(get_repository)):
    return repo.create(body.model_dump(mode="json"))


@router.patch("/{schedule_id}", response_model=HorarioAulaOut)
def patch_horario_aula(
    schedule_id: UUID, body: HorarioAulaPatch,
    repo: HorarioAulaRepository = Depends(get_repository),
):
    return repo.patch(schedule_id, body.model_dump(mode="json", exclude_unset=True))


@router.delete("/{schedule_id}", status_code=204)
def delete_horario_aula(schedule_id: UUID, repo: HorarioAulaRepository = Depends(get_repository)):
    repo.delete(schedule_id)
    return Response(status_code=204)
