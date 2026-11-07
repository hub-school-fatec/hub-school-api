from typing import Annotated

from io import BytesIO

from fastapi import APIRouter, Depends, Response, Request, Query
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.errors import DomainError

from app.dependencies.auth import get_current_user_id
from app.integrations.contracts import AccountGateway, AttachmentGateway, get_account_gateway, get_attachment_gateway
from app.routers.academic import Service
from app.schemas.academic import Error
from app.schemas.planning import (Attachment, Calculation, CalculationInput, DeletionRequest,
                                  Export, Reminder, ReminderInput, Situation, SituationInput)
from app.services.planning import calculate, reminders, situation
from app.services.attachments import validate_attachment


router = APIRouter(dependencies=[Depends(get_current_user_id)], responses={
    401: {'description': 'Bearer ausente ou inválido'},
    404: {'model': Error, 'description': 'Recurso inexistente ou não acessível'},
    503: {'model': Error, 'description': 'Integração indisponível'},
})
User = Annotated[str, Depends(get_current_user_id)]


@router.post('/calculos/aprovacao', response_model=Calculation, tags=['calculos'],
             description='Simulação para uma avaliação restante. A escala máxima é informada explicitamente. Não grava dados.')
def approval(payload: CalculationInput):
    return calculate(payload)


@router.post('/calculos/situacao', response_model=Situation, tags=['calculos'],
             description='Avalia RN03 sem inventar precedência: critérios conflitantes ou insuficientes retornam situação nula.')
def academic_situation(payload: SituationInput):
    return situation(payload)


@router.post('/eventos/{event_id}/previa-lembretes', response_model=list[Reminder], tags=['notificacoes'],
             description='Prévia de datas, sem agendar nem enviar e-mails. Padrão: 3 e 1 dias antes.')
def reminder_preview(event_id: str, payload: ReminderInput, service: Service):
    return reminders(service, event_id, payload)


@router.get('/conta/exportacao', response_model=Export, tags=['conta'],
            description='Contrato de exportação completa. Indisponível até integração de Auth, banco e Storage.')
def export_account(user_id: User, gateway: Annotated[AccountGateway, Depends(get_account_gateway)]):
    result = gateway.export(user_id)
    if result.usuario_id != user_id:
        raise DomainError(500, 'Resposta de integração inválida.')
    return result


@router.delete('/conta', status_code=204, tags=['conta'],
               description='Exclusão integral depende de fluxo autorizado externo; atualmente retorna 503.')
def delete_account(payload: DeletionRequest, user_id: User,
                   gateway: Annotated[AccountGateway, Depends(get_account_gateway)]):
    gateway.delete(user_id)
    return Response(status_code=204)


@router.get('/anotacoes/{note_id}/anexos', response_model=list[Attachment], tags=['anexos'])
def attachments(note_id: str, service: Service,
                gateway: Annotated[AttachmentGateway, Depends(get_attachment_gateway)]):
    service.get('anotacoes', note_id)
    result = gateway.list(service.user_id, note_id)
    if any(item.anotacao_id != note_id for item in result):
        raise DomainError(500, 'Resposta de integração inválida.')
    return result


@router.post('/anotacoes/{note_id}/anexos', response_model=Attachment, status_code=201, tags=['anexos'],
             responses={413: {'description': 'Arquivo muito grande'}, 415: {'description': 'Formato não aceito'}},
             description='Corpo binário application/octet-stream; nome_arquivo na query. '
             'PDF, PNG, JPEG, GIF e WebP. Storage não integrado; limite provisório configurável.',
             openapi_extra={'requestBody': {'required': True, 'content': {
                 'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}}})
async def upload_attachment(request: Request, note_id: str, service: Service,
                            gateway: Annotated[AttachmentGateway, Depends(get_attachment_gateway)],
                            nome_arquivo: Annotated[str, Query(min_length=1, max_length=500)]):
    await run_in_threadpool(service.get, 'anotacoes', note_id)
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > settings.attachment_max_bytes:
            raise DomainError(413, 'Arquivo excede o limite configurado.')
        content.extend(chunk)
    validate_attachment(nome_arquivo, bytes(content))
    # Run synchronous storage adapters outside the event loop.
    result = await run_in_threadpool(gateway.upload, service.user_id, note_id, nome_arquivo, BytesIO(content))
    if result.anotacao_id != note_id:
        raise DomainError(500, 'Resposta de integração inválida.')
    return result
