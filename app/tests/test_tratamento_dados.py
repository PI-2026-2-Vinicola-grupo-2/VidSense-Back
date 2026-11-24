from datetime import datetime, timezone

from app.models.db_models import LeituraClimatica
from app.services import thingspeak_client
from app.services.ingestion_service import sincronizar_leituras


def _feed(entry_id, temperatura=25.0, umidade=60.0):
    return {
        "entry_id": entry_id,
        "temperatura": temperatura,
        "umidade": umidade,
        "umidade_solo": None,
        "registrado_em": datetime.now(timezone.utc).isoformat(),
    }


def test_descarta_temperatura_fora_da_faixa(db_session, monkeypatch):
    feeds = [_feed(301, temperatura=999.0), _feed(302)]
    monkeypatch.setattr(thingspeak_client, "get_historico", lambda resultados=100: feeds)

    novos = sincronizar_leituras(db_session, 10)

    assert novos == 1
    ids = [l.entry_id for l in db_session.query(LeituraClimatica).all()]
    assert 301 not in ids
    assert 302 in ids


def test_descarta_umidade_nula(db_session, monkeypatch):
    feeds = [_feed(311, umidade=None), _feed(312)]
    monkeypatch.setattr(thingspeak_client, "get_historico", lambda resultados=100: feeds)

    novos = sincronizar_leituras(db_session, 10)

    assert novos == 1
    ids = [l.entry_id for l in db_session.query(LeituraClimatica).all()]
    assert 311 not in ids


def test_duplicata_no_mesmo_lote_nao_quebra_a_sincronizacao(db_session, monkeypatch):
    feeds = [_feed(321), _feed(321)]
    monkeypatch.setattr(thingspeak_client, "get_historico", lambda resultados=100: feeds)

    novos = sincronizar_leituras(db_session, 10)

    assert novos == 1