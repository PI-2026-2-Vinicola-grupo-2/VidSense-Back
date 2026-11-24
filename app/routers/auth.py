from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models.db_models import UsuarioDB
from app.models.usuario import Perfil, Token, UsuarioLogin, UsuarioRegistro

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, dados: UsuarioRegistro, db: Session = Depends(get_db)):
    if dados.perfil != Perfil.produtor_exportador:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Perfil restrito: solicite a um administrador",
        )
    if db.query(UsuarioDB).filter(UsuarioDB.email == dados.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-mail já cadastrado")
    usuario = UsuarioDB(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_password(dados.senha),
        perfil=dados.perfil.value,
        organizacao=dados.organizacao,
    )
    db.add(usuario)
    db.commit()
    return {"mensagem": "Usuário criado com sucesso"}


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, dados: UsuarioLogin, db: Session = Depends(get_db)):
    usuario = db.query(UsuarioDB).filter(UsuarioDB.email == dados.email).first()
    if not usuario or not verify_password(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos")
    token = create_access_token(subject=usuario.email, role=usuario.perfil, org=usuario.organizacao)
    return Token(
        access_token=token, nome=usuario.nome, perfil=usuario.perfil, organizacao=usuario.organizacao
    )