import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models.alertas import AlertaHistoricoOut, AlertaOut
from app.services import thingspeak_client
from app.services.alertas_service import calcular_alertas, listar_historico, registrar_historico

router = APIRouter(prefix="/alertas", tags=["alertas"])
log = logging.getLogger(__name__)

PERFIS = ("produtor_exportador", "analista_dados", "administrador")


@router.get("", response_model=list[AlertaOut])
def listar_alertas(
    usuario=Depends(require_role(*PERFIS)),
    db: Session = Depends(get_db),
):
    atual = thingspeak_client.get_ultima_leitura()
    alertas = calcular_alertas(atual)
    try:
        registrar_historico(db, alertas)
    except Exception:
        # Se o banco falhar, os alertas atuais continuam sendo entregues
        log.exception("Falha ao registrar histórico de alertas")
        db.rollback()
    return alertas


@router.get("/historico", response_model=list[AlertaHistoricoOut])
def historico_alertas(
    limite: int = Query(50, ge=1, le=500),
    usuario=Depends(require_role(*PERFIS)),
    db: Session = Depends(get_db),
):
    return listar_historico(db, limite)