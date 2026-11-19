from datetime import datetime, timezone

from app.models.db_models import AlertaEmitido
from app.services import thingspeak_client
from app.services.ingestion_service import sincronizar_leituras


def test_sincronizacao_emite_alerta_sem_consultar_a_tela(db_session, monkeypatch):
    feed = {
        "entry_id": 201,
        "temperatura": 25.0,
        "umidade": 90.0,
        "umidade_solo": None,
        "registrado_em": datetime.now(timezone.utc).isoformat(),
    }
    monkeypatch.setattr(thingspeak_client, "get_historico", lambda resultados=100: [feed])

    novos = sincronizar_leituras(db_session, 10)

    assert novos == 1
    chaves = [a.chave for a in db_session.query(AlertaEmitido).all()]
    assert "umidade_alta-201" in chaves


def test_sincronizacao_com_leitura_velha_nao_emite_alerta(db_session, monkeypatch):
    from datetime import timedelta

    feed = {
        "entry_id": 202,
        "temperatura": 40.0,
        "umidade": 99.0,
        "umidade_solo": None,
        "registrado_em": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
    }
    monkeypatch.setattr(thingspeak_client, "get_historico", lambda resultados=100: [feed])

    sincronizar_leituras(db_session, 10)

    chaves = [a.chave for a in db_session.query(AlertaEmitido).all()]
    assert not any(c.endswith("-202") for c in chaves)