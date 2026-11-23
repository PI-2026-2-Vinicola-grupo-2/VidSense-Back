def test_mercado_resumo_exige_login(client):
    assert client.get("/mercado/resumo").status_code == 401


def test_mercado_resumo_retorna_serie_e_destinos(client, token_analista):
    resposta = client.get(
        "/mercado/resumo",
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["serie_precos"]) >= 2
    assert corpo["demanda_por_destino"]
    assert corpo["origem"] == "simulado"