from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.academic import Contract, Identifier, NonNegative, Positive, Text


class WeightedGrade(Contract):
    nota: NonNegative
    peso: Positive


class CalculationInput(Contract):
    avaliacoes_lancadas: Annotated[list[WeightedGrade], Field(max_length=1000)]
    peso_proxima: Positive
    nota_maxima: Positive

    @model_validator(mode='after')
    def scale(self):
        if any(a.nota > self.nota_maxima for a in self.avaliacoes_lancadas):
            raise ValueError('Nota acima da escala informada.')
        return self


class Calculation(Contract):
    nota_minima: Decimal
    impossivel: bool
    media_maxima: Decimal
    media_alvo: Decimal


class SituationInput(Contract):
    presenca_percentual: Annotated[Decimal, Field(ge=0, le=100, allow_inf_nan=False)]
    faltas: Annotated[int, Field(ge=0, strict=True)]
    limite_faltas: Annotated[int, Field(ge=0, strict=True)]
    media: NonNegative | None = None
    media_maxima_possivel: NonNegative | None = None
    nota_minima_proxima: NonNegative | None = None


class Situation(Contract):
    criterios_acionados: list[Literal['aprovado', 'em_risco', 'reprovado']]
    situacao: Literal['aprovado', 'em_risco', 'reprovado'] | None
    requer_definicao: bool


class ReminderInput(Contract):
    antecedencia_dias: Annotated[list[Annotated[int, Field(ge=0, strict=True)]], Field(min_length=1, max_length=20)] = [3, 1]
    canal: Literal['email'] = 'email'


class Reminder(Contract):
    evento_id: Identifier
    canal: Literal['email']
    enviar_em: AwareDatetime


class Attachment(Contract):
    id: Identifier
    anotacao_id: Identifier
    nome_arquivo: Text
    tamanho_bytes: Annotated[int, Field(gt=0)]


class Export(Contract):
    usuario_id: Identifier
    gerado_em: AwareDatetime
    dados: dict[str, list[dict]]


class DeletionRequest(Contract):
    confirmar_exclusao: Literal[True]


class GroupInput(Contract):
    nome: Text


class Group(GroupInput):
    id: Identifier
    criado_por: Identifier
    codigo_convite: Text


class MessageInput(Contract):
    texto: Annotated[str, Field(min_length=1, max_length=20000)]


class Message(MessageInput):
    id: Identifier
    grupo_id: Identifier
    usuario_id: Identifier
    enviada_em: datetime
