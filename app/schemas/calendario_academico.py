from datetime import date

from pydantic import BaseModel


class CalendarioAcademicoOut(BaseModel):
    id: str
    data: date
    tipo: str
    descricao: str
