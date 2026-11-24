"""Isolamento entre organizações: uma organização nunca enxerga dados da outra.

A organização vem do token assinado no login (claim `org`), nunca do corpo da requisição.
"""
import pytest
from cryptography.fernet import Fernet
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token
from app.models.db_models import ClienteDB, UsuarioDB

CLIENTE_A = {"nome": "Importadora Rhein GmbH", "pais": "Alemanha", "documento": "12.345.678/0001-90"}
CLIENTE_B = {"nome": "Fruits du Sud SARL", "pais": "França", "documento": "FR-998877665"}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def chave(monkeypatch):
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())


@pytest.fixture
def admin_b():
    return create_access_token(subject="admin@agrosul.com", role="administrador", org="org-b")


@pytest.fixture
def analista_b():
    return create_access_token(subject="analista@agrosul.com", role="analista_dados", org="org-b")


# ---------- clientes ----------

def test_organizacao_b_nao_ve_clientes_da_a(client, token_admin, admin_b, analista_b):
    client.post("/clientes", json=CLIENTE_A, headers=_auth(token_admin))
    assert client.get("/clientes", headers=_auth(admin_b)).json() == []
    assert client.get("/clientes", headers=_auth(analista_b)).json() == []


def test_detalhe_de_cliente_de_outra_organizacao_retorna_404(client, token_admin, admin_b):
    criado = client.post("/clientes", json=CLIENTE_A, headers=_auth(token_admin)).json()
    resposta = client.get(f"/clientes/{criado['id']}", headers=_auth(admin_b))
    assert resposta.status_code == 404
    assert "12.345.678" not in resposta.text


def test_cada_organizacao_ve_so_os_proprios_clientes(client, token_admin, admin_b):
    client.post("/clientes", json=CLIENTE_A, headers=_auth(token_admin))
    client.post("/clientes", json=CLIENTE_B, headers=_auth(admin_b))
    nomes_a = [c["nome"] for c in client.get("/clientes", headers=_auth(token_admin)).json()]
    nomes_b = [c["nome"] for c in client.get("/clientes", headers=_auth(admin_b)).json()]
    assert nomes_a == [CLIENTE_A["nome"]]
    assert nomes_b == [CLIENTE_B["nome"]]


def test_organizacao_do_cliente_vem_do_token_e_nao_do_corpo(client, db_session, admin_b):
    corpo = {**CLIENTE_B, "organizacao": "org-a"}  # tentativa de gravar na organização alheia
    assert client.post("/clientes", json=corpo, headers=_auth(admin_b)).status_code == 201
    assert db_session.query(ClienteDB).one().organizacao == "org-b"


# ---------- usuários (rotas do administrador) ----------

@pytest.fixture
def usuarios_das_duas_orgs(db_session):
    a = UsuarioDB(nome="Prod A", email="prod@a.com", senha_hash="x", perfil="produtor_exportador", organizacao="org-a")
    b = UsuarioDB(nome="Prod B", email="prod@b.com", senha_hash="x", perfil="produtor_exportador", organizacao="org-b")
    db_session.add_all([a, b])
    db_session.commit()
    return a, b


def test_admin_lista_so_usuarios_da_propria_organizacao(client, usuarios_das_duas_orgs, token_admin, admin_b):
    emails_a = [u["email"] for u in client.get("/admin/usuarios", headers=_auth(token_admin)).json()]
    emails_b = [u["email"] for u in client.get("/admin/usuarios", headers=_auth(admin_b)).json()]
    assert "prod@a.com" in emails_a and "prod@b.com" not in emails_a
    assert "prod@b.com" in emails_b and "prod@a.com" not in emails_b


def test_admin_nao_altera_perfil_de_usuario_de_outra_organizacao(client, usuarios_das_duas_orgs, admin_b):
    usuario_a, _ = usuarios_das_duas_orgs
    resposta = client.patch(
        f"/admin/usuarios/{usuario_a.id}/perfil", json={"perfil": "administrador"}, headers=_auth(admin_b)
    )
    assert resposta.status_code == 404


def test_usuario_criado_pelo_admin_nasce_na_organizacao_dele(client, db_session, admin_b):
    corpo = {"nome": "Novo", "email": "novo@agrosul.com", "senha": "senha-forte-123",
             "perfil": "analista_dados", "organizacao": "org-a"}
    resposta = client.post("/admin/usuarios", json=corpo, headers=_auth(admin_b))
    assert resposta.status_code == 201
    assert db_session.query(UsuarioDB).filter_by(email="novo@agrosul.com").one().organizacao == "org-b"


def test_so_admin_cria_usuario(client, token_produtor, token_analista):
    corpo = {"nome": "X", "email": "x@x.com", "senha": "senha-forte-123", "perfil": "analista_dados"}
    assert client.post("/admin/usuarios", json=corpo, headers=_auth(token_produtor)).status_code == 403
    assert client.post("/admin/usuarios", json=corpo, headers=_auth(token_analista)).status_code == 403


# ---------- token e cadastro ----------

def test_cadastro_com_organizacao_vai_para_o_token(client):
    corpo = {"nome": "Maria", "email": "maria@agrosul.com", "senha": "senha-forte-123",
             "perfil": "produtor_exportador", "organizacao": "org-b"}
    assert client.post("/auth/register", json=corpo).status_code == 201
    login = client.post("/auth/login", json={"email": "maria@agrosul.com", "senha": "senha-forte-123"})
    assert login.json()["organizacao"] == "org-b"
    claims = jwt.decode(login.json()["access_token"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert claims["org"] == "org-b"


def test_cadastro_sem_organizacao_usa_a_padrao(client):
    corpo = {"nome": "Joao", "email": "joao@vinicola.com", "senha": "senha-forte-123", "perfil": "produtor_exportador"}
    client.post("/auth/register", json=corpo)
    login = client.post("/auth/login", json={"email": "joao@vinicola.com", "senha": "senha-forte-123"})
    assert login.json()["organizacao"] == "org-a"


@pytest.mark.parametrize("org", ["ORG B", "org_b", "a", "org/b", "x" * 41])
def test_organizacao_invalida_retorna_422(client, org):
    corpo = {"nome": "Z", "email": "z@z.com", "senha": "senha-forte-123",
             "perfil": "produtor_exportador", "organizacao": org}
    assert client.post("/auth/register", json=corpo).status_code == 422


def test_token_sem_organizacao_e_recusado(client):
    antigo = create_access_token(subject="admin@vinicola.com", role="administrador", org=None)
    assert client.get("/clientes", headers=_auth(antigo)).status_code == 401
    assert client.get("/admin/usuarios", headers=_auth(antigo)).status_code == 401
