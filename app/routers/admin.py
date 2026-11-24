from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, org_do_usuario, require_role
from app.models.db_models import UsuarioDB
from app.models.usuario import Perfil, UsuarioRegistro

router = APIRouter(prefix="/admin", tags=["admin"])


class UsuarioAdminOut(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    organizacao: str

    model_config = {"from_attributes": True}


class PerfilUpdate(BaseModel):
    perfil: Perfil


@router.get("/usuarios", response_model=list[UsuarioAdminOut])
def listar_usuarios(
    db: Session = Depends(get_db),
    admin=Depends(require_role("administrador")),
):
    org = org_do_usuario(admin)
    return db.query(UsuarioDB).filter(UsuarioDB.organizacao == org).order_by(UsuarioDB.id).all()


@router.post("/usuarios", response_model=UsuarioAdminOut, status_code=status.HTTP_201_CREATED)
def criar_usuario(
    dados: UsuarioRegistro,
    db: Session = Depends(get_db),
    admin=Depends(require_role("administrador")),
):
    if db.query(UsuarioDB).filter(UsuarioDB.email == dados.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-mail já cadastrado")

    usuario = UsuarioDB(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_password(dados.senha),
        perfil=dados.perfil.value,
        organizacao=org_do_usuario(admin),  # o novo usuário nasce na organização de quem o criou
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch("/usuarios/{usuario_id}/perfil", response_model=UsuarioAdminOut)
def alterar_perfil(
    usuario_id: int,
    dados: PerfilUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_role("administrador")),
):
    org = org_do_usuario(admin)
    alvo = db.get(UsuarioDB, usuario_id)
    # usuário de outra organização é tratado como inexistente (não revela que existe)
    if alvo is None or alvo.organizacao != org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    if alvo.email == admin.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O administrador não pode alterar o próprio perfil",
        )
    alvo.perfil = dados.perfil.value
    db.commit()
    db.refresh(alvo)
    return alvo