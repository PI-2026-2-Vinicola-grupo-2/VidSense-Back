"""Gestão de secrets: nenhuma chave, senha ou token pode estar no código-fonte.

Evidência automatizada para a entrega de Segurança: os valores reais vêm de
variáveis de ambiente (.env local / painel do Render) e o .env nunca vai ao GitHub.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings

RAIZ = Path(__file__).resolve().parents[2]

VARIAVEIS_SENSIVEIS = [
    "JWT_SECRET_KEY",
    "THINGSPEAK_READ_API_KEY",
    "DB_HOST",
    "DB_USER",
    "DB_PASSWORD",
]

# nome sensível = "literal longo" | URL com usuário:senha@host
PADRAO_SEGREDO = re.compile(
    r"""(?ix)
    (api[_-]?key|secret|passw(or)?d|senha|token)\w*\s*[:=]\s*["'][A-Za-z0-9_@!#$%^&*./+\-]{12,}["']
    |postgres(ql)?(\+\w+)?://[^\s:@/]+:[^\s@/]+@
    """
)


def _arquivos_de_codigo():
    for caminho in [RAIZ / "main.py", *(RAIZ / "app").rglob("*.py")]:
        if "tests" not in caminho.parts:
            yield caminho


def test_env_esta_no_gitignore():
    linhas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in [linha.strip() for linha in linhas]


@pytest.mark.skipif(shutil.which("git") is None, reason="git indisponível")
def test_env_nao_e_versionado():
    resultado = subprocess.run(
        ["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True
    )
    if resultado.returncode != 0:
        pytest.skip("fora de um repositório git")
    versionados = resultado.stdout.splitlines()
    perigosos = [
        f for f in versionados
        if re.search(r"(^|/)\.env$|\.pem$|\.key$|\.db$", f)
    ]
    assert perigosos == []


def test_jwt_secret_e_obrigatorio(monkeypatch):
    """Sem JWT_SECRET_KEY a aplicação não sobe: não existe chave padrão no código."""
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_credenciais_nao_tem_valor_padrao(monkeypatch):
    """Chaves de terceiros e do banco vêm vazias por padrão; o valor real vem do ambiente."""
    for nome in VARIAVEIS_SENSIVEIS:
        monkeypatch.delenv(nome, raising=False)
    config = Settings(jwt_secret_key="valor-de-teste", _env_file=None)
    assert config.thingspeak_read_api_key == ""
    assert config.db_password == ""
    assert config.db_user == ""
    assert config.db_host == ""


def test_codigo_fonte_sem_segredos_hardcoded():
    encontrados = []
    for caminho in _arquivos_de_codigo():
        texto = caminho.read_text(encoding="utf-8")
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if PADRAO_SEGREDO.search(linha):
                encontrados.append(f"{caminho.relative_to(RAIZ)}:{numero}")
    assert encontrados == []
