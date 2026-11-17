from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Response

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.anotacoes import AnotacaoRepository
from app.repositories.supabase import PostgrestClient
from app.routers.semestres import get_http_client
from app.schemas.anotacao import AnotacaoCreate, AnotacaoOut, AnotacaoPatch


router = APIRouter(prefix="/anotacoes", tags=["anotacoes"])


def get_repository(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    client: httpx.Client = Depends(get_http_client),
) -> AnotacaoRepository:
    return AnotacaoRepository(
        PostgrestClient(client, table="anotacao"),
        PostgrestClient(client, table="disciplina"),
        PostgrestClient(client, table="evento"),
        identity,
        PostgrestClient(client, table="anexo"),
    )


@router.get("", response_model=list[AnotacaoOut])
def list_anotacoes(disciplina_id: UUID | None = None, evento_id: UUID | None = None,
                   repo: AnotacaoRepository = Depends(get_repository)):
    return repo.list(disciplina_id, evento_id)


@router.get("/{note_id}", response_model=AnotacaoOut)
def get_anotacao(note_id: UUID, repo: AnotacaoRepository = Depends(get_repository)):
    return repo.get(note_id)


@router.post("", response_model=AnotacaoOut, status_code=201)
def create_anotacao(body: AnotacaoCreate, repo: AnotacaoRepository = Depends(get_repository)):
    return repo.create(body.model_dump(mode="json"))


@router.patch("/{note_id}", response_model=AnotacaoOut)
def patch_anotacao(note_id: UUID, body: AnotacaoPatch,
                   repo: AnotacaoRepository = Depends(get_repository)):
    return repo.patch(note_id, body.model_dump(mode="json", exclude_unset=True))


@router.delete("/{note_id}", status_code=204)
def delete_anotacao(note_id: UUID, repo: AnotacaoRepository = Depends(get_repository)):
    repo.delete(note_id)
    return Response(status_code=204)
