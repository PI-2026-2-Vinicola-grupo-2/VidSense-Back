from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DadoMercadoBase(BaseModel):
    produto: str = Field(min_length=2, max_length=120)
    preco: float = Field(gt=0, allow_inf_nan=False)
    demanda: str | None = Field(default=None, max_length=40)
    registrado_em: datetime | None = None


class DadoMercadoCreate(DadoMercadoBase):
    pass


class DadoMercadoUpdate(BaseModel):
    produto: str | None = Field(default=None, min_length=2, max_length=120)
    preco: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    demanda: str | None = Field(default=None, max_length=40)
    registrado_em: datetime | None = None


class DadoMercadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produto: str
    preco: float
    demanda: str | None = None
    registrado_em: datetime
