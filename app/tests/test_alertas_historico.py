from datetime import datetime, timezone


def _leitura(entry_id, temperatura, umidade):
    return {
        "entry_id": entry_id,
        "temperatura": temperatura,
        "umidade": umidade,
        "umidade_solo": None,
        "registrado_em": datetime.now(timezone.utc).isoformat(),
    }


def test_alerta_de_risco_entra_no_historico_uma_vez(client, token_analista, monkeypatch):
    from app.services import thingspeak_client

    headers = {"Authorization": f"Bearer {token_analista}"}
    monkeypatch.setattr(thingspeak_client, "get_ultima_leitura", lambda: _leitura(101, 25.0, 90.0))

    client.get("/alertas", headers=headers)
    client.get("/alertas", headers=headers)  # segunda consulta não duplica

    historico = client.get("/alertas/historico", headers=headers).json()
    ids = [h["id"] for h in historico]
    assert ids.count("umidade_alta-101") == 1


def test_janela_ideal_gera_alerta_informativo(client, token_analista, monkeypatch):
    from app.services import thingspeak_client

    headers = {"Authorization": f"Bearer {token_analista}"}
    monkeypatch.setattr(thingspeak_client, "get_ultima_leitura", lambda: _leitura(102, 25.0, 60.0))

    atuais = client.get("/alertas", headers=headers).json()
    assert atuais[0]["id"] == "janela_ideal-102"
    assert atuais[0]["tipo"] == "info"

    historico = client.get("/alertas/historico", headers=headers).json()
    assert "janela_ideal-102" in [h["id"] for h in historico]


def test_leitura_velha_nao_vai_para_o_historico(client, token_analista, monkeypatch):
    from datetime import timedelta
    from app.services import thingspeak_client

    headers = {"Authorization": f"Bearer {token_analista}"}
    leitura = _leitura(103, 40.0, 99.0)
    leitura["registrado_em"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    monkeypatch.setattr(thingspeak_client, "get_ultima_leitura", lambda: leitura)

    client.get("/alertas", headers=headers)
    historico = client.get("/alertas/historico", headers=headers).json()
    assert not any(h["id"].endswith("-103") for h in historico)