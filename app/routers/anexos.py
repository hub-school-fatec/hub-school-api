from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.anexos import AnexoRepository
from app.repositories.storage import StorageClient
from app.repositories.supabase import PostgrestClient
from app.routers.semestres import get_http_client
from app.schemas.anexo import AnexoPublic
from app.services.anexos import AnexoService


router = APIRouter(prefix="/anexos", tags=["anexos"])


def get_service(identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
                client: httpx.Client = Depends(get_http_client)) -> AnexoService:
    repository = AnexoRepository(PostgrestClient(client, table="anexo"),
                                 PostgrestClient(client, table="anotacao"), identity)
    return AnexoService(repository, StorageClient(client), identity)


@router.get("", response_model=list[AnexoPublic])
def list_anexos(anotacao_id: UUID | None = None,
                service: AnexoService = Depends(get_service)):
    return service.list(anotacao_id)


@router.post("/upload", response_model=AnexoPublic, status_code=201)
def upload_anexo(anotacao_id: UUID = Form(...), arquivo: UploadFile = File(...),
                 service: AnexoService = Depends(get_service)):
    return service.upload(anotacao_id, arquivo)


@router.get("/{attachment_id}", response_model=AnexoPublic)
def get_anexo(attachment_id: UUID, service: AnexoService = Depends(get_service)):
    return service.get(attachment_id)


@router.get("/{attachment_id}/download")
def download_anexo(attachment_id: UUID, service: AnexoService = Depends(get_service)):
    record, data = service.download(attachment_id)
    return Response(content=data, media_type=record.tipo_mime,
                    headers={"Content-Disposition": f'attachment; filename="{record.nome_arquivo}"',
                             "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.delete("/{attachment_id}", status_code=204)
def delete_anexo(attachment_id: UUID, service: AnexoService = Depends(get_service)):
    service.delete(attachment_id)
    return Response(status_code=204)
