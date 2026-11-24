from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.crypto import cifrar, decifrar, mascarar
from app.core.database import get_db
from app.core.security import org_do_usuario, require_role
from app.models.db_models import ClienteDB

router = APIRouter(prefix="/clientes", tags=["clientes"])


class ClienteCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    pais: str = Field(min_length=2, max_length=60)
    documento: str = Field(min_length=3, max_length=40)


class ClienteResumo(BaseModel):
    id: int
    nome: str
    pais: str
    documento_mascarado: str


class ClienteDetalhe(BaseModel):
    id: int
    nome: str
    pais: str
    documento: str


def _resumo(cliente: ClienteDB) -> ClienteResumo:
    return ClienteResumo(
        id=cliente.id,
        nome=cliente.nome,
        pais=cliente.pais,
        documento_mascarado=mascarar(decifrar(cliente.documento_cifrado)),
    )


@router.post("", response_model=ClienteResumo, status_code=status.HTTP_201_CREATED)
def cadastrar_cliente(
    dados: ClienteCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_role("administrador")),
):
    cliente = ClienteDB(
        nome=dados.nome,
        pais=dados.pais,
        documento_cifrado=cifrar(dados.documento),  # cifra antes de guardar
        organizacao=org_do_usuario(admin),  # vem do token, nunca do corpo da requisição
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return _resumo(cliente)


@router.get("", response_model=list[ClienteResumo])
def listar_clientes(
    db: Session = Depends(get_db),
    usuario=Depends(require_role("analista_dados", "administrador")),
):
    """Lista com o documento mascarado: o valor completo só aparece no detalhe, para o administrador."""
    org = org_do_usuario(usuario)
    clientes = db.query(ClienteDB).filter(ClienteDB.organizacao == org).order_by(ClienteDB.id).all()
    return [_resumo(c) for c in clientes]


@router.get("/{cliente_id}", response_model=ClienteDetalhe)
def detalhar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_role("administrador")),
):
    cliente = db.get(ClienteDB, cliente_id)
    # cliente de outra organização é tratado como inexistente (não revela que existe)
    if cliente is None or cliente.organizacao != org_do_usuario(admin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado")
    return ClienteDetalhe(
        id=cliente.id,
        nome=cliente.nome,
        pais=cliente.pais,
        documento=decifrar(cliente.documento_cifrado),  # decifra só para exibir
    )
