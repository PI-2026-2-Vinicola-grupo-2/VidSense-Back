import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.db_models import DadoMercado

# Convenção de armazenamento (tabela dados_mercado):
#   preço diário  -> produto="uva_mesa", preco=R$/kg, registrado_em=dia
#   demanda       -> produto="demanda", preco=toneladas, demanda=nome do destino
#   índice        -> produto="demanda_indice", preco=0 a 100
PRODUTO_PRECO = "uva_mesa"
PRODUTO_DEMANDA = "demanda"
PRODUTO_INDICE = "demanda_indice"
DIAS_SERIE = 90

DESTINOS = [
    ("Europa", 420),
    ("Estados Unidos", 310),
    ("Reino Unido", 180),
    ("Mercado interno", 260),
]


def _preco_simulado(i: int) -> float:
    return round(11 + 1.3 * math.sin(i / 11) + 0.4 * math.sin(i / 3.1), 2)


def garantir_dados_simulados(db: Session) -> None:
    """Gera a série simulada uma única vez. Chamadas seguintes não duplicam nada."""
    ja_existe = db.query(DadoMercado.id).filter(DadoMercado.produto == PRODUTO_PRECO).first()
    if ja_existe:
        return

    hoje = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(DIAS_SERIE):
        dia = hoje - timedelta(days=DIAS_SERIE - 1 - i)
        db.add(DadoMercado(produto=PRODUTO_PRECO, preco=_preco_simulado(i), demanda=None, registrado_em=dia))

    for destino, toneladas in DESTINOS:
        db.add(DadoMercado(produto=PRODUTO_DEMANDA, preco=float(toneladas), demanda=destino, registrado_em=hoje))

    db.add(DadoMercado(produto=PRODUTO_INDICE, preco=78.0, demanda=None, registrado_em=hoje))
    db.commit()


def montar_resumo(db: Session) -> dict:
    garantir_dados_simulados(db)

    precos = (
        db.query(DadoMercado)
        .filter(DadoMercado.produto == PRODUTO_PRECO)
        .order_by(DadoMercado.registrado_em.asc())
        .all()
    )
    serie = [{"data": p.registrado_em.date().isoformat(), "preco": p.preco} for p in precos]
    atual = serie[-1]["preco"]
    anterior = serie[-2]["preco"] if len(serie) > 1 else atual
    variacao = round((atual - anterior) / anterior * 100, 1) if anterior else 0.0

    destinos = db.query(DadoMercado).filter(DadoMercado.produto == PRODUTO_DEMANDA).all()
    indice = (
        db.query(DadoMercado)
        .filter(DadoMercado.produto == PRODUTO_INDICE)
        .order_by(DadoMercado.id.desc())
        .first()
    )

    return {
        "origem": "simulado",
        "preco_atual": atual,
        "variacao_pct": variacao,
        "demanda_indice": indice.preco if indice else None,
        "serie_precos": serie,
        "demanda_por_destino": [{"destino": d.demanda, "toneladas": d.preco} for d in destinos],
    }