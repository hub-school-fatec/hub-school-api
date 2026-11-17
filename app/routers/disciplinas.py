from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Response

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.disciplinas import DisciplinaRepository
from app.repositories.supabase import PostgrestClient
from app.routers.semestres import get_http_client
from app.schemas.disciplina import DisciplinaCreate, DisciplinaOut, DisciplinaPatch


router = APIRouter(prefix="/disciplinas", tags=["disciplinas"])


def get_repository(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    client: httpx.Client = Depends(get_http_client),
) -> DisciplinaRepository:
    return DisciplinaRepository(
        PostgrestClient(client, table="disciplina"),
        PostgrestClient(client, table="semestre"),
        PostgrestClient(client, table="docente"),
        identity,
    )


@router.get("", response_model=list[DisciplinaOut])
def list_disciplinas(
    semestre_id: UUID | None = None, docente_id: UUID | None = None,
    repo: DisciplinaRepository = Depends(get_repository),
):
    return repo.list(semestre_id, docente_id)


@router.get("/{discipline_id}", response_model=DisciplinaOut)
def get_disciplina(discipline_id: UUID, repo: DisciplinaRepository = Depends(get_repository)):
    return repo.get(discipline_id)


@router.post("", response_model=DisciplinaOut, status_code=201)
def create_disciplina(body: DisciplinaCreate, repo: DisciplinaRepository = Depends(get_repository)):
    return repo.create(body.model_dump(mode="json"))


@router.patch("/{discipline_id}", response_model=DisciplinaOut)
def patch_disciplina(
    discipline_id: UUID, body: DisciplinaPatch,
    repo: DisciplinaRepository = Depends(get_repository),
):
    return repo.patch(discipline_id, body.model_dump(mode="json", exclude_unset=True))


@router.delete("/{discipline_id}", status_code=204)
def delete_disciplina(discipline_id: UUID, repo: DisciplinaRepository = Depends(get_repository)):
    repo.delete(discipline_id)
    return Response(status_code=204)
