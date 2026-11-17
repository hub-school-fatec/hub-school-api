from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Response

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.avaliacoes import AvaliacaoRepository
from app.repositories.supabase import PostgrestClient
from app.routers.semestres import get_http_client
from app.schemas.avaliacao import AvaliacaoCreate, AvaliacaoOut, AvaliacaoPatch


router = APIRouter(prefix="/avaliacoes", tags=["avaliacoes"])


def get_repository(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    client: httpx.Client = Depends(get_http_client),
) -> AvaliacaoRepository:
    return AvaliacaoRepository(
        PostgrestClient(client, table="avaliacao"),
        PostgrestClient(client, table="disciplina"),
        identity,
    )


@router.get("", response_model=list[AvaliacaoOut])
def list_avaliacoes(disciplina_id: UUID | None = None,
                   repo: AvaliacaoRepository = Depends(get_repository)):
    return repo.list(disciplina_id)


@router.get("/{evaluation_id}", response_model=AvaliacaoOut)
def get_avaliacao(evaluation_id: UUID, repo: AvaliacaoRepository = Depends(get_repository)):
    return repo.get(evaluation_id)


@router.post("", response_model=AvaliacaoOut, status_code=201)
def create_avaliacao(body: AvaliacaoCreate, repo: AvaliacaoRepository = Depends(get_repository)):
    return repo.create(body.model_dump(mode="json"))


@router.patch("/{evaluation_id}", response_model=AvaliacaoOut)
def patch_avaliacao(evaluation_id: UUID, body: AvaliacaoPatch,
                   repo: AvaliacaoRepository = Depends(get_repository)):
    return repo.patch(evaluation_id, body.model_dump(mode="json", exclude_unset=True))


@router.delete("/{evaluation_id}", status_code=204)
def delete_avaliacao(evaluation_id: UUID, repo: AvaliacaoRepository = Depends(get_repository)):
    repo.delete(evaluation_id)
    return Response(status_code=204)
