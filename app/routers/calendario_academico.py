import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.dependencies.identity import AuthenticatedIdentity, get_authenticated_identity
from app.repositories.supabase import PostgrestClient
from app.routers.semestres import get_http_client
from app.schemas.calendario_academico import CalendarioAcademicoOut


router = APIRouter(prefix="/calendario-academico", tags=["calendario-academico"])


@router.get("", response_model=list[CalendarioAcademicoOut])
def list_calendario_academico(
    identity: AuthenticatedIdentity = Depends(get_authenticated_identity),
    client: httpx.Client = Depends(get_http_client),
) -> list[CalendarioAcademicoOut]:
    rows = PostgrestClient(client, table="calendario_academico").request(
        "GET", identity.access_token, {"select": "id,data,tipo,descricao"},
    )
    try:
        return [CalendarioAcademicoOut.model_validate(row) for row in rows]
    except ValidationError:
        raise HTTPException(503, "Serviço indisponível") from None
