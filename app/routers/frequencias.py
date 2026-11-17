from datetime import date
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Response

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.frequencias import FrequenciaRepository
from app.repositories.supabase import PostgrestClient
from app.routers.semestres import get_http_client
from app.schemas.frequencia import FrequenciaCreate, FrequenciaOut, FrequenciaPatch


router = APIRouter(prefix="/frequencias", tags=["frequencias"])


def get_repository(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    client: httpx.Client = Depends(get_http_client),
) -> FrequenciaRepository:
    return FrequenciaRepository(
        PostgrestClient(client, table="frequencia"),
        PostgrestClient(client, table="disciplina"),
        identity,
    )


@router.get("", response_model=list[FrequenciaOut])
def list_frequencias(
    disciplina_id: UUID | None = None, data: date | None = None,
    repo: FrequenciaRepository = Depends(get_repository),
):
    return repo.list(disciplina_id, data)


@router.get("/{frequency_id}", response_model=FrequenciaOut)
def get_frequencia(frequency_id: UUID, repo: FrequenciaRepository = Depends(get_repository)):
    return repo.get(frequency_id)


@router.post("", response_model=FrequenciaOut, status_code=201)
def create_frequencia(body: FrequenciaCreate, repo: FrequenciaRepository = Depends(get_repository)):
    return repo.create(body.model_dump(mode="json"))


@router.patch("/{frequency_id}", response_model=FrequenciaOut)
def patch_frequencia(
    frequency_id: UUID, body: FrequenciaPatch,
    repo: FrequenciaRepository = Depends(get_repository),
):
    return repo.patch(frequency_id, body.model_dump(mode="json", exclude_unset=True))


@router.delete("/{frequency_id}", status_code=204)
def delete_frequencia(frequency_id: UUID, repo: FrequenciaRepository = Depends(get_repository)):
    repo.delete(frequency_id)
    return Response(status_code=204)
