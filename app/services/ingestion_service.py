import logging
import math
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.db_models import LeituraClimatica
from app.services import thingspeak_client
from app.services.alertas_service import calcular_alertas, registrar_historico

log = logging.getLogger(__name__)

# Faixas aceitas para os sensores (RF05)
TEMP_MIN, TEMP_MAX = -10.0, 60.0
UMI_MIN, UMI_MAX = 0.0, 100.0


def _numero_valido(valor, minimo, maximo) -> bool:
    if valor is None:
        return False
    try:
        x = float(valor)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x) and minimo <= x <= maximo


def _limpar(feed: dict) -> dict | None:
    """Devolve a leitura pronta para gravar, ou None se ela deve ser descartada."""
    if feed.get("entry_id") is None or not feed.get("registrado_em"):
        return None
    if not _numero_valido(feed.get("temperatura"), TEMP_MIN, TEMP_MAX):
        return None
    if not _numero_valido(feed.get("umidade"), UMI_MIN, UMI_MAX):
        return None

    limpo = dict(feed)
    limpo["temperatura"] = float(feed["temperatura"])
    limpo["umidade"] = float(feed["umidade"])
    solo = feed.get("umidade_solo")
    limpo["umidade_solo"] = float(solo) if _numero_valido(solo, UMI_MIN, UMI_MAX) else None
    return limpo


def _data_registro(reg) -> datetime:
    if isinstance(reg, datetime):
        return reg if reg.tzinfo else reg.replace(tzinfo=timezone.utc)
    if isinstance(reg, str):
        try:
            dt = datetime.fromisoformat(reg.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def sincronizar_leituras(db: Session, resultados: int = 500) -> int:
    try:
        feeds = thingspeak_client.get_historico(resultados)
    except Exception:
        return 0

    # Limpeza: descarta inválidas e duplicadas dentro do próprio lote
    limpos = []
    vistos = set()
    for feed in feeds:
        limpo = _limpar(feed)
        if limpo is None or limpo["entry_id"] in vistos:
            continue
        vistos.add(limpo["entry_id"])
        limpos.append(limpo)

    descartadas = len(feeds) - len(limpos)
    if descartadas:
        log.info("RF05: %d leitura(s) descartada(s) por valor inválido, nulo ou duplicado", descartadas)
    if not limpos:
        return 0

    ids = [f["entry_id"] for f in limpos]
    existentes = {
        e for (e,) in db.query(LeituraClimatica.entry_id).filter(LeituraClimatica.entry_id.in_(ids))
    }

    novos = 0
    for f in limpos:
        if f["entry_id"] in existentes:
            continue
        db.add(LeituraClimatica(
            entry_id=f["entry_id"],
            temperatura=f["temperatura"],
            umidade=f["umidade"],
            umidade_solo=f["umidade_solo"],
            registrado_em=_data_registro(f["registrado_em"]),
        ))
        novos += 1

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return 0
    except Exception:
        db.rollback()
        return 0

    if novos:
        _emitir_alertas_da_ultima_leitura(db, limpos)

    return novos


def _emitir_alertas_da_ultima_leitura(db: Session, limpos: list[dict]) -> None:
    """Avalia a leitura mais recente e grava os alertas no histórico."""
    try:
        ultimo = max(limpos, key=lambda f: f["entry_id"])
        alertas = calcular_alertas(ultimo)
        registrar_historico(db, alertas)
    except Exception:
        db.rollback()