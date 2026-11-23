"""Criptografia de dados sensíveis em repouso (Fernet: AES-128-CBC + HMAC-SHA256).

A chave vem da variável de ambiente ENCRYPTION_KEY (painel do Render / .env local)
e nunca fica no código. Para gerar uma chave:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.core.config import settings


def _fernet() -> Fernet:
    if not settings.encryption_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Criptografia não configurada no servidor",
        )
    try:
        return Fernet(settings.encryption_key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chave de criptografia inválida no servidor",
        )


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode("utf-8")).decode("ascii")


def decifrar(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível decifrar o dado (chave diferente da usada ao cifrar)",
        )


def mascarar(texto: str, visiveis: int = 4) -> str:
    """Mostra só os últimos caracteres: '12.345.678/0001-90' -> '*************1-90'."""
    if len(texto) <= visiveis:
        return "*" * len(texto)
    return "*" * (len(texto) - visiveis) + texto[-visiveis:]
