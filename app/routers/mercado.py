from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models.db_models import DadoMercado
from app.models.mercado import DadoMercadoCreate, DadoMercadoOut, DadoMercadoUpdate

router = APIRouter(prefix="/mercado", tags=["mercado"])

LEITURA_ROLES = ("produtor_exportador", "analista_dados", "administrador")
ESCRITA_ROLES = ("analista_dados", "administrador")


@router.get("", response_model=list[DadoMercadoOut])
def listar_dados_mercado(
    produto: str | None = Query(default=None, min_length=1, max_length=120),
    data_inicio: datetime | None = None,
    data_fim: datetime | None = None,
    limite: int = Query(default=100, ge=1, le=500),
    deslocamento: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    usuario=Depends(require_role(*LEITURA_ROLES)),
):
    consulta = db.query(DadoMercado)
    if produto:
        consulta = consulta.filter(DadoMercado.produto.ilike(f"%{produto.strip()}%"))
    if data_inicio:
        consulta = consulta.filter(DadoMercado.registrado_em >= data_inicio)
    if data_fim:
        consulta = consulta.filter(DadoMercado.registrado_em <= data_fim)
    return (
        consulta.order_by(DadoMercado.registrado_em.desc(), DadoMercado.id.desc())
        .offset(deslocamento)
        .limit(limite)
        .all()
    )


@router.get("/{dado_id}", response_model=DadoMercadoOut)
def obter_dado_mercado(
    dado_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_role(*LEITURA_ROLES)),
):
    dado = db.query(DadoMercado).filter(DadoMercado.id == dado_id).first()
    if dado is None:
        raise HTTPException(status_code=404, detail="Registro de mercado não encontrado")
    return dado


@router.post("", response_model=DadoMercadoOut, status_code=status.HTTP_201_CREATED)
def criar_dado_mercado(
    dados: DadoMercadoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(require_role(*ESCRITA_ROLES)),
):
    registro = DadoMercado(
        produto=dados.produto.strip(),
        preco=dados.preco,
        demanda=dados.demanda.strip() if dados.demanda else None,
        registrado_em=dados.registrado_em or datetime.now(timezone.utc),
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


@router.patch("/{dado_id}", response_model=DadoMercadoOut)
def atualizar_dado_mercado(
    dado_id: int,
    dados: DadoMercadoUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(require_role(*ESCRITA_ROLES)),
):
    registro = db.query(DadoMercado).filter(DadoMercado.id == dado_id).first()
    if registro is None:
        raise HTTPException(status_code=404, detail="Registro de mercado não encontrado")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if campo == "produto" and valor is not None:
            valor = valor.strip()
        if campo == "demanda" and valor is not None:
            valor = valor.strip() or None
        setattr(registro, campo, valor)
    db.commit()
    db.refresh(registro)
    return registro


@router.delete("/{dado_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_dado_mercado(
    dado_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_role("administrador")),
):
    registro = db.query(DadoMercado).filter(DadoMercado.id == dado_id).first()
    if registro is None:
        raise HTTPException(status_code=404, detail="Registro de mercado não encontrado")
    db.delete(registro)
    db.commit()
