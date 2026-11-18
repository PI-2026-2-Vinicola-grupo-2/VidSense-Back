"""RF12: só o administrador lista usuários e altera perfis (200 / 401 / 403)."""
import pytest

from app.core.security import create_access_token
from app.models.db_models import UsuarioDB


@pytest.fixture
def usuarios(db_session):
    prod = UsuarioDB(nome="Prod", email="prod@vinicola.com", senha_hash="x", perfil="produtor_exportador")
    adm = UsuarioDB(nome="Adm", email="admin@vinicola.com", senha_hash="x", perfil="administrador")
    db_session.add_all([prod, adm])
    db_session.commit()
    return prod, adm


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_admin_lista_usuarios(client, usuarios, token_admin):
    r = client.get("/admin/usuarios", headers=_auth(token_admin))
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()]
    assert "prod@vinicola.com" in emails
    assert "senha_hash" not in r.json()[0]


@pytest.mark.parametrize("fixture_token", ["token_produtor", "token_analista"])
def test_nao_admin_recebe_403_ao_listar(client, request, fixture_token):
    r = client.get("/admin/usuarios", headers=_auth(request.getfixturevalue(fixture_token)))
    assert r.status_code == 403


def test_sem_token_recebe_401(client):
    assert client.get("/admin/usuarios").status_code == 401


def test_admin_altera_perfil(client, usuarios, token_admin):
    prod, _ = usuarios
    r = client.patch(
        f"/admin/usuarios/{prod.id}/perfil",
        json={"perfil": "analista_dados"},
        headers=_auth(token_admin),
    )
    assert r.status_code == 200
    assert r.json()["perfil"] == "analista_dados"


@pytest.mark.parametrize("fixture_token", ["token_produtor", "token_analista"])
def test_nao_admin_recebe_403_ao_alterar(client, request, usuarios, fixture_token):
    prod, _ = usuarios
    r = client.patch(
        f"/admin/usuarios/{prod.id}/perfil",
        json={"perfil": "administrador"},
        headers=_auth(request.getfixturevalue(fixture_token)),
    )
    assert r.status_code == 403


def test_perfil_invalido_retorna_422(client, usuarios, token_admin):
    prod, _ = usuarios
    r = client.patch(
        f"/admin/usuarios/{prod.id}/perfil", json={"perfil": "superuser"}, headers=_auth(token_admin)
    )
    assert r.status_code == 422


def test_usuario_inexistente_retorna_404(client, token_admin):
    r = client.patch("/admin/usuarios/99999/perfil", json={"perfil": "analista_dados"}, headers=_auth(token_admin))
    assert r.status_code == 404


def test_admin_nao_altera_o_proprio_perfil(client, usuarios, token_admin):
    _, adm = usuarios
    r = client.patch(f"/admin/usuarios/{adm.id}/perfil", json={"perfil": "produtor_exportador"}, headers=_auth(token_admin))
    assert r.status_code == 400
