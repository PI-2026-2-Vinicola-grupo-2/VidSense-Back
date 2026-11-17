import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_role
from app.models.clima import LeituraOut, SincronizacaoOut
from app.models.db_models import LeituraClimatica
from app.services import thingspeak_client
from app.services.ingestion_service import sincronizar_leituras

router = APIRouter(prefix="/clima", tags=["clima"])

_ultimo_sync: float = 0.0


def _enriquecer_leitura(leitura: dict) -> dict:
    reg = leitura.get("registrado_em")
    dt = None
    if isinstance(reg, datetime):
        dt = reg if reg.tzinfo else reg.replace(tzinfo=timezone.utc)
    elif isinstance(reg, str):
        try:
            dt = datetime.fromisoformat(reg.replace("Z", "+00:00"))
        except ValueError:
            dt = None

    defasagem = None
    desatualizado = False
    if dt:
        agora = datetime.now(timezone.utc)
        defasagem = int((agora - dt).total_seconds() // 60)
        desatualizado = defasagem > settings.stale_minutes

    res = dict(leitura)
    res["defasagem_minutos"] = defasagem
    res["desatualizado"] = desatualizado
    if dt:
        res["registrado_em"] = dt
    return res


@router.get("/atual", response_model=LeituraOut)
def clima_atual():
    return _enriquecer_leitura(thingspeak_client.get_ultima_leitura())


@router.get("/historico", response_model=list[LeituraOut])
def clima_historico(
    horas: int | None = Query(None, ge=1, le=720),
    resultados: int = 100,
    db: Session = Depends(get_db),
    usuario=Depends(require_role("analista_dados", "administrador")),
):
    global _ultimo_sync
    if horas is not None:
        agora_ts = time.time()
        if agora_ts - _ultimo_sync >= 60.0:
            try:
                sincronizar_leituras(db, 100)
                _ultimo_sync = time.time()
            except IntegrityError:
                db.rollback()
            except Exception:
                pass

        agora = datetime.now(timezone.utc)
        limite = agora - timedelta(hours=horas)
        leituras_db = (
            db.query(LeituraClimatica)
            .filter(LeituraClimatica.registrado_em >= limite)
            .order_by(LeituraClimatica.registrado_em.asc())
            .all()
        )
        if leituras_db:
            return [
                _enriquecer_leitura({
                    "entry_id": l.entry_id,
                    "temperatura": l.temperatura,
                    "umidade": l.umidade,
                    "umidade_solo": l.umidade_solo,
                    "registrado_em": l.registrado_em,
                })
                for l in leituras_db
            ]
        else:
            return [_enriquecer_leitura(l) for l in thingspeak_client.get_historico(resultados)]

    return [_enriquecer_leitura(l) for l in thingspeak_client.get_historico(resultados)]


@router.post("/sincronizar", response_model=SincronizacaoOut)
def sincronizar(
    resultados: int = 500,
    db: Session = Depends(get_db),
    usuario=Depends(require_role("administrador")),
):
    return {"novas_leituras": sincronizar_leituras(db, min(resultados, 8000))}