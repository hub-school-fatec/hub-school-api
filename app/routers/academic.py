from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime

from app.core.errors import DomainError
from app.dependencies.academic import get_service
from app.schemas.academic import (
    Assessment, AssessmentInput, Attendance, AttendanceInput, AttendanceSummary, Average,
    CalendarItem, Contract, Error, Event, EventInput, Lesson, Note, NoteInput, Onboarding,
    Schedule, ScheduleInput, Semester, SemesterInput, Subject, SubjectInput, Teacher, TeacherInput,
)
from app.services.academic import AcademicService


router = APIRouter(responses={
    401: {'description': 'Bearer ausente ou inválido'},
    404: {'model': Error, 'description': 'Recurso inexistente ou não acessível'},
    409: {'model': Error, 'description': 'Conflito de estado ou vínculos'},
    503: {'model': Error, 'description': 'Persistência não integrada'},
})
Service = Annotated[AcademicService, Depends(get_service)]


def public(row: dict, model: type[Contract]) -> Contract:
    return model.model_validate({k: v for k, v in row.items() if k in model.model_fields})


def register_resource(entity: str, input_model: type[Contract], output_model: type[Contract], *, delete: bool = False):
    """Build identical owner-scoped CRUD plumbing with concrete OpenAPI schemas."""
    def listing(
        service: Service,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        disciplina_id: str | None = None,
        semestre_id: str | None = None,
        evento_id: str | None = None,
        texto: Annotated[str | None, Query(max_length=500)] = None,
        tipo: Literal['prova', 'trabalho', 'apresentacao', 'aula', 'evento'] | None = None,
        inicio: AwareDatetime | None = None,
        fim: AwareDatetime | None = None,
    ):
        if inicio is not None and fim is not None and fim <= inicio:
            raise DomainError(422, 'Intervalo inválido.')
        for key, target, value in [('disciplina_id', 'disciplinas', disciplina_id),
                                   ('semestre_id', 'semestres', semestre_id),
                                   ('evento_id', 'eventos', evento_id)]:
            if value is not None:
                if key not in output_model.model_fields:
                    raise DomainError(422, 'Filtro não aplicável a este recurso.')
                service.get(target, value)
        if (inicio is not None or fim is not None) and entity != 'eventos':
            raise DomainError(422, 'Filtro temporal disponível para eventos.')
        if tipo is not None and entity != 'eventos':
            raise DomainError(422, 'Filtro por tipo disponível para eventos.')
        rows = service.list(entity)
        if tipo is not None:
            rows = [r for r in rows if r['tipo'] == tipo]
        for key, value in [('disciplina_id', disciplina_id), ('semestre_id', semestre_id), ('evento_id', evento_id)]:
            if value is not None:
                rows = [r for r in rows if r.get(key) == value]
        if texto:
            rows = [r for r in rows if texto.casefold() in ' '.join(
                str(r.get(k, '')) for k in ('nome', 'titulo', 'corpo')).casefold()]
        if inicio is not None:
            rows = [r for r in rows if r['fim'] > inicio]
        if fim is not None:
            rows = [r for r in rows if r['inicio'] < fim]
        rows = sorted(rows, key=lambda r: r['id'])
        return [public(r, output_model) for r in rows[offset:offset + limit]]

    def read(record_id: str, service: Service):
        return public(service.get(entity, record_id), output_model)

    def create(payload, service: Service):
        return public(service.save(entity, payload), output_model)

    def update(record_id: str, payload, service: Service):
        return public(service.save(entity, payload, record_id), output_model)

    create.__annotations__['payload'] = input_model
    update.__annotations__['payload'] = input_model
    for method, path, handler, response, status in [
        ('GET', f'/{entity}', listing, list[output_model], 200),
        ('GET', f'/{entity}/{{record_id}}', read, output_model, 200),
        ('POST', f'/{entity}', create, output_model, 201),
        ('PUT', f'/{entity}/{{record_id}}', update, output_model, 200),
    ]:
        router.add_api_route(path, handler, methods=[method], response_model=response,
                             status_code=status, tags=[entity], name=f'{entity}_{handler.__name__}',
                             description='Dados privados do estudante autenticado. PUT substitui todos os campos editáveis. '
                             'Persistência real pendente; retorna 503 até integração.')
    if delete:
        def remove(record_id: str, service: Service):
            service.delete(entity, record_id)
            return Response(status_code=204)
        router.add_api_route(f'/{entity}/{{record_id}}', remove, methods=['DELETE'],
                             status_code=204, tags=[entity], name=f'{entity}_delete',
                             description='Exclui recurso próprio sem vínculos dependentes.')


for entity, incoming, outgoing, deletable in [
    ('semestres', SemesterInput, Semester, False),
    ('docentes', TeacherInput, Teacher, True),
    ('disciplinas', SubjectInput, Subject, False),
    ('horarios', ScheduleInput, Schedule, False),
    ('frequencias', AttendanceInput, Attendance, False),
    ('avaliacoes', AssessmentInput, Assessment, False),
    ('eventos', EventInput, Event, False),
    ('anotacoes', NoteInput, Note, True),
]:
    register_resource(entity, incoming, outgoing, delete=deletable)


@router.get('/disciplinas/{record_id}/resumo-frequencia', response_model=AttendanceSummary, tags=['frequencias'])
def attendance_summary(record_id: str, service: Service):
    return service.attendance(record_id)


@router.get('/disciplinas/{record_id}/media', response_model=Average, tags=['avaliacoes'],
            description='Média parcial apenas das notas lançadas; notas nulas não equivalem a zero.')
def subject_average(record_id: str, service: Service):
    return service.average(record_id)


@router.get('/primeiro-acesso', response_model=Onboarding, tags=['primeiro-acesso'],
            description='Retoma dados salvos. Não inventa etapas nem marcador de conclusão.')
def onboarding(service: Service):
    return {entity: [public(r, model) for r in service.list(entity)] for entity, model in [
        ('semestres', Semester), ('disciplinas', Subject), ('horarios', Schedule), ('docentes', Teacher)]}


@router.get('/calendario-academico', response_model=list[CalendarItem], tags=['agenda'])
def calendar(service: Service, inicio: date | None = None, fim: date | None = None):
    if inicio and fim and fim < inicio:
        raise DomainError(422, 'Intervalo inválido.')
    return [public(r, CalendarItem) for r in service.repo.calendar()
            if (inicio is None or r['data'] >= inicio) and (fim is None or r['data'] <= fim)]


@router.get('/aulas-recorrentes', response_model=list[Lesson], tags=['agenda'],
            description='Projeção dos horários dentro do semestre, sem gravar eventos. '
            'Não exclui feriados automaticamente: política de cancelamento pendente. Horários locais.')
def recurring_lessons(service: Service, inicio: date, fim: date):
    return service.lessons(inicio, fim)
