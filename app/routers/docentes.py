from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Response

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.docentes import DocenteRepository
from app.repositories.supabase import PostgrestClient
from app.routers.semestres import get_http_client
from app.schemas.docente import DocenteCreate, DocenteOut, DocentePatch


router = APIRouter(prefix="/docentes", tags=["docentes"])


def get_repository(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    client: httpx.Client = Depends(get_http_client),
) -> DocenteRepository:
    return DocenteRepository(PostgrestClient(client, table="docente"), identity)


@router.get("", response_model=list[DocenteOut])
def list_docentes(repo: DocenteRepository = Depends(get_repository)):
    return repo.list()


@router.get("/{teacher_id}", response_model=DocenteOut)
def get_docente(teacher_id: UUID, repo: DocenteRepository = Depends(get_repository)):
    return repo.get(teacher_id)


@router.post("", response_model=DocenteOut, status_code=201)
def create_docente(body: DocenteCreate, repo: DocenteRepository = Depends(get_repository)):
    return repo.create(body.model_dump(mode="json"))


@router.patch("/{teacher_id}", response_model=DocenteOut)
def patch_docente(teacher_id: UUID, body: DocentePatch, repo: DocenteRepository = Depends(get_repository)):
    return repo.patch(teacher_id, body.model_dump(mode="json", exclude_unset=True))


@router.delete("/{teacher_id}", status_code=204)
def delete_docente(teacher_id: UUID, repo: DocenteRepository = Depends(get_repository)):
    repo.delete(teacher_id)
    return Response(status_code=204)
