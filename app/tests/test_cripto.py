"""Criptografia de dado sensível: cifrar, guardar, decifrar e exibir (documento do cliente)."""
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from app.core import crypto
from app.core.config import settings
from app.models.db_models import ClienteDB

DOCUMENTO = "12.345.678/0001-90"
CLIENTE = {"nome": "Importadora Rhein GmbH", "pais": "Alemanha", "documento": DOCUMENTO}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def chave(monkeypatch):
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())


# ---------- módulo de criptografia ----------

def test_cifra_e_decifra_volta_ao_original():
    assert crypto.decifrar(crypto.cifrar(DOCUMENTO)) == DOCUMENTO


def test_texto_cifrado_nao_revela_o_original():
    cifrado = crypto.cifrar(DOCUMENTO)
    assert cifrado != DOCUMENTO
    assert DOCUMENTO not in cifrado
    assert cifrado.startswith("gAAAA")  # formato do token Fernet


def test_mesmo_texto_gera_cifras_diferentes():
    assert crypto.cifrar(DOCUMENTO) != crypto.cifrar(DOCUMENTO)


def test_chave_diferente_nao_decifra(monkeypatch):
    cifrado = crypto.cifrar(DOCUMENTO)
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
    with pytest.raises(HTTPException) as erro:
        crypto.decifrar(cifrado)
    assert erro.value.status_code == 500


def test_sem_chave_configurada_retorna_503(monkeypatch):
    monkeypatch.setattr(settings, "encryption_key", "")
    with pytest.raises(HTTPException) as erro:
        crypto.cifrar(DOCUMENTO)
    assert erro.value.status_code == 503


def test_mascara_mostra_so_o_final():
    assert crypto.mascarar(DOCUMENTO).endswith("1-90")
    assert DOCUMENTO not in crypto.mascarar(DOCUMENTO)
    assert crypto.mascarar("abc") == "***"


# ---------- fluxo completo pela API ----------

def test_banco_guarda_somente_o_valor_cifrado(client, db_session, token_admin):
    resposta = client.post("/clientes", json=CLIENTE, headers=_auth(token_admin))
    assert resposta.status_code == 201
    guardado = db_session.query(ClienteDB).one().documento_cifrado
    assert guardado != DOCUMENTO
    assert DOCUMENTO not in guardado
    assert guardado.startswith("gAAAA")


def test_admin_ve_o_documento_decifrado(client, token_admin):
    criado = client.post("/clientes", json=CLIENTE, headers=_auth(token_admin)).json()
    detalhe = client.get(f"/clientes/{criado['id']}", headers=_auth(token_admin))
    assert detalhe.status_code == 200
    assert detalhe.json()["documento"] == DOCUMENTO


def test_analista_ve_a_lista_com_documento_mascarado(client, token_admin, token_analista):
    client.post("/clientes", json=CLIENTE, headers=_auth(token_admin))
    lista = client.get("/clientes", headers=_auth(token_analista))
    assert lista.status_code == 200
    item = lista.json()[0]
    assert "documento" not in item
    assert item["documento_mascarado"].endswith("1-90")
    assert DOCUMENTO not in lista.text


def test_cliente_inexistente_retorna_404(client, token_admin):
    assert client.get("/clientes/99999", headers=_auth(token_admin)).status_code == 404


# ---------- RBAC do recurso ----------

@pytest.mark.parametrize(
    "metodo,rota,perfil,esperado",
    [
        ("POST", "/clientes", "produtor", 403),
        ("POST", "/clientes", "analista", 403),
        ("GET", "/clientes", "produtor", 403),
        ("GET", "/clientes", "analista", 200),
        ("GET", "/clientes/1", "produtor", 403),
        ("GET", "/clientes/1", "analista", 403),
    ],
)
def test_permissoes_por_perfil(client, request, metodo, rota, perfil, esperado):
    token = request.getfixturevalue(f"token_{perfil}")
    corpo = CLIENTE if metodo == "POST" else None
    resposta = client.request(metodo, rota, json=corpo, headers=_auth(token))
    assert resposta.status_code == esperado


@pytest.mark.parametrize("metodo,rota", [("POST", "/clientes"), ("GET", "/clientes"), ("GET", "/clientes/1")])
def test_sem_token_retorna_401(client, metodo, rota):
    corpo = CLIENTE if metodo == "POST" else None
    assert client.request(metodo, rota, json=corpo).status_code == 401
