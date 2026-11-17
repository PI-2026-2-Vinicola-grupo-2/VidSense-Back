"""Prova do RBAC no back-end: 200 (permitido), 401 (sem login) e 403 (sem permissão).

Os testes chamam a API direto, sem passar pelo front-end, então mostram que o
bloqueio acontece no servidor e não depende de botões ocultos.
"""
import pytest

PERFIS = ("produtor", "analista", "admin")

# (método, rota) -> perfis que PODEM acessar
MATRIZ = {
    ("GET", "/clima/historico?horas=24"): {"analista", "admin"},
    ("POST", "/clima/sincronizar"): {"admin"},
    ("GET", "/alertas"): {"produtor", "analista", "admin"},
    ("GET", "/previsao/janela-colheita"): {"produtor", "analista", "admin"},
}


def _headers(request, perfil):
    token = request.getfixturevalue(f"token_{perfil}")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("rota", MATRIZ.keys(), ids=lambda r: f"{r[0]} {r[1]}")
@pytest.mark.parametrize("perfil", PERFIS)
def test_matriz_de_permissoes(client, request, rota, perfil):
    metodo, caminho = rota
    resposta = client.request(metodo, caminho, headers=_headers(request, perfil))
    esperado = 200 if perfil in MATRIZ[rota] else 403
    assert resposta.status_code == esperado, resposta.text


@pytest.mark.parametrize("rota", MATRIZ.keys(), ids=lambda r: f"{r[0]} {r[1]}")
def test_sem_token_retorna_401(client, rota):
    metodo, caminho = rota
    assert client.request(metodo, caminho).status_code == 401


def test_403_tem_mensagem_clara(client, token_produtor):
    resposta = client.get(
        "/clima/historico?horas=24",
        headers={"Authorization": f"Bearer {token_produtor}"},
    )
    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "Sem permissão para este recurso"


def test_role_forjada_no_token_e_rejeitada(client):
    """Quem altera o token por conta própria não consegue virar admin (assinatura inválida)."""
    from jose import jwt

    falso = jwt.encode(
        {"sub": "hacker@x.com", "role": "administrador"}, "outra-chave", algorithm="HS256"
    )
    resposta = client.post("/clima/sincronizar", headers={"Authorization": f"Bearer {falso}"})
    assert resposta.status_code == 401
