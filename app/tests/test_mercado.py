def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_mercado_exige_autenticacao(client):
    assert client.get("/mercado").status_code == 401


def test_criar_listar_e_obter_dado_mercado(client, token_analista):
    headers = auth(token_analista)
    criado = client.post("/mercado", headers=headers, json={
        "produto": "Uva Isabel",
        "preco": 12.5,
        "demanda": "alta",
    })
    assert criado.status_code == 201
    dado = criado.json()
    assert dado["produto"] == "Uva Isabel"
    assert dado["preco"] == 12.5
    assert dado["demanda"] == "alta"
    assert dado["registrado_em"]

    lista = client.get("/mercado?produto=Isabel", headers=headers)
    assert lista.status_code == 200
    assert len(lista.json()) == 1
    assert client.get(f"/mercado/{dado['id']}", headers=headers).json()["id"] == dado["id"]


def test_produtor_pode_consultar_mas_nao_cadastrar(client, token_produtor):
    headers = auth(token_produtor)
    assert client.get("/mercado", headers=headers).status_code == 200
    resposta = client.post("/mercado", headers=headers, json={
        "produto": "Uva Itália", "preco": 15.0
    })
    assert resposta.status_code == 403


def test_validacao_preco_e_obrigatoria(client, token_analista):
    resposta = client.post("/mercado", headers=auth(token_analista), json={
        "produto": "Uva", "preco": -1
    })
    assert resposta.status_code == 422


def test_atualizar_e_excluir_com_permissao(client, token_analista, token_admin):
    headers_analista = auth(token_analista)
    criado = client.post("/mercado", headers=headers_analista, json={
        "produto": "Uva", "preco": 10
    })
    dado_id = criado.json()["id"]

    atualizado = client.patch(f"/mercado/{dado_id}", headers=headers_analista, json={
        "preco": 11.75, "demanda": "média"
    })
    assert atualizado.status_code == 200
    assert atualizado.json()["preco"] == 11.75
    assert atualizado.json()["demanda"] == "média"

    assert client.delete(f"/mercado/{dado_id}", headers=headers_analista).status_code == 403
    assert client.delete(f"/mercado/{dado_id}", headers=auth(token_admin)).status_code == 204
    assert client.get(f"/mercado/{dado_id}", headers=headers_analista).status_code == 404
