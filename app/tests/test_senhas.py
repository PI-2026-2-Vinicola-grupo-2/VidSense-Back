"""Proteção de senhas: o banco guarda apenas o hash bcrypt, nunca a senha em texto puro."""
from app.core.security import hash_password, verify_password
from app.models.db_models import UsuarioDB

SENHA = "senha-bem-secreta-123"


def _cadastrar(client, email="protegido@example.com"):
    resposta = client.post(
        "/auth/register",
        json={"nome": "Usuário Teste", "email": email, "senha": SENHA, "perfil": "produtor_exportador"},
    )
    assert resposta.status_code == 201


def test_senha_nao_e_guardada_em_texto_puro(client, db_session):
    _cadastrar(client)
    usuario = db_session.query(UsuarioDB).filter_by(email="protegido@example.com").one()
    assert usuario.senha_hash != SENHA
    assert SENHA not in usuario.senha_hash


def test_hash_no_banco_e_bcrypt(client, db_session):
    _cadastrar(client)
    usuario = db_session.query(UsuarioDB).filter_by(email="protegido@example.com").one()
    assert usuario.senha_hash.startswith("$2b$")
    custo = int(usuario.senha_hash.split("$")[2])
    assert custo >= 10


def test_mesma_senha_gera_hashes_diferentes():
    """Cada hash usa um salt próprio: dois usuários com a mesma senha não têm o mesmo hash."""
    assert hash_password(SENHA) != hash_password(SENHA)


def test_login_funciona_com_a_senha_original(client):
    _cadastrar(client)
    certo = client.post("/auth/login", json={"email": "protegido@example.com", "senha": SENHA})
    errado = client.post("/auth/login", json={"email": "protegido@example.com", "senha": SENHA + "x"})
    assert certo.status_code == 200
    assert errado.status_code == 401


def test_verify_password_rejeita_senha_errada():
    hashed = hash_password(SENHA)
    assert verify_password(SENHA, hashed) is True
    assert verify_password("outra-senha", hashed) is False
