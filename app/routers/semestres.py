from collections.abc import Iterator
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Response

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.semestres import SemestreRepository
from app.repositories.supabase import PostgrestClient
from app.schemas.semestre import SemestreCreate, SemestreOut, SemestrePatch


router = APIRouter(prefix="/semestres", tags=["semestres"])


def get_http_client() -> Iterator[httpx.Client]:
    with httpx.Client() as client:
        yield client


def get_repository(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    client: httpx.Client = Depends(get_http_client),
) -> SemestreRepository:
    return SemestreRepository(PostgrestClient(client), identity)


@router.get("", response_model=list[SemestreOut])
def list_semestres(repo: SemestreRepository = Depends(get_repository)):
    return repo.list()


@router.get("/{semester_id}", response_model=SemestreOut)
def get_semestre(semester_id: UUID, repo: SemestreRepository = Depends(get_repository)):
    return repo.get(semester_id)


@router.post("", response_model=SemestreOut, status_code=201)
def create_semestre(body: SemestreCreate, repo: SemestreRepository = Depends(get_repository)):
    return repo.create(body.model_dump(mode="json"))


@router.patch("/{semester_id}", response_model=SemestreOut)
def patch_semestre(semester_id: UUID, body: SemestrePatch, repo: SemestreRepository = Depends(get_repository)):
    return repo.patch(semester_id, body.model_dump(mode="json", exclude_unset=True))


@router.delete("/{semester_id}", status_code=204)
def delete_semestre(semester_id: UUID, repo: SemestreRepository = Depends(get_repository)):
    repo.delete(semester_id)
    return Response(status_code=204)
