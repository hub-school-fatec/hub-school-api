from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


class FrequenciaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID
    data: date
    aulas_no_dia: StrictInt = Field(gt=0)
    faltas: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def check(self):
        if self.faltas > self.aulas_no_dia:
            raise ValueError("Faltas excedem aulas no dia")
        return self


class FrequenciaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disciplina_id: UUID | None = None
    data: date | None = None
    aulas_no_dia: StrictInt | None = Field(default=None, gt=0)
    faltas: StrictInt | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check(self):
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Alteração inválida")
        if self.aulas_no_dia is not None and self.faltas is not None and self.faltas > self.aulas_no_dia:
            raise ValueError("Faltas excedem aulas no dia")
        return self


class FrequenciaOut(BaseModel):
    id: UUID
    usuario_id: UUID
    disciplina_id: UUID
    data: date
    aulas_no_dia: int
    faltas: int
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None
