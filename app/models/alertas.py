from typing import Literal
from pydantic import BaseModel


class AlertaOut(BaseModel):
    id: str
    tipo: Literal["ok", "info", "warn"]
    titulo: str
    desc: str
    quando: str
    temperatura: float | None = None
    umidade: float | None = None
    umidade_solo: float | None = None


class AlertaHistoricoOut(BaseModel):
    id: str
    tipo: Literal["info", "warn"]
    titulo: str
    desc: str
    quando: str
    emitido_em: str | None = None