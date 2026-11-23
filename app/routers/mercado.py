from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.services.mercado_service import montar_resumo

router = APIRouter(prefix="/mercado", tags=["mercado"])

PERFIS = ("produtor_exportador", "analista_dados", "administrador")


@router.get("/resumo")
def resumo_mercado(
    usuario=Depends(require_role(*PERFIS)),
    db: Session = Depends(get_db),
):
    return montar_resumo(db)