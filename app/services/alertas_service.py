from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import AlertaEmitido


def _data(reg):
    """Devolve (datetime ou None, texto de quando)."""
    if isinstance(reg, datetime):
        dt = reg if reg.tzinfo else reg.replace(tzinfo=timezone.utc)
        return dt, dt.isoformat()
    if isinstance(reg, str):
        try:
            dt = datetime.fromisoformat(reg.replace("Z", "+00:00"))
        except ValueError:
            dt = None
        return dt, reg
    return None, ""


def _iso(valor):
    if valor is None:
        return None
    return valor.isoformat() if hasattr(valor, "isoformat") else str(valor)


def calcular_alertas(atual: dict) -> list[dict]:
    entry_id = atual.get("entry_id") or 0
    temperatura = atual.get("temperatura")
    umidade = atual.get("umidade")
    umidade_solo = atual.get("umidade_solo")
    dt, quando = _data(atual.get("registrado_em"))

    base = {
        "quando": quando,
        "temperatura": temperatura,
        "umidade": umidade,
        "umidade_solo": umidade_solo,
    }

    if dt:
        defasagem = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
        if defasagem > settings.stale_minutes:
            return [{
                "id": f"sem_leituras_recentes-{entry_id}",
                "tipo": "info",
                "titulo": "Sem leituras recentes",
                "desc": f"Última leitura registrada em {quando} (há {defasagem} minutos).",
                **base,
            }]

    alertas = []

    def adicionar(regra, tipo, titulo, desc):
        alertas.append({"id": f"{regra}-{entry_id}", "tipo": tipo, "titulo": titulo, "desc": desc, **base})

    if umidade is not None and umidade > settings.alerta_umidade_alta:
        adicionar("umidade_alta", "warn",
                  f"Umidade acima de {settings.alerta_umidade_alta:.0f}%",
                  "Risco aumentado de fungos. Verifique a área monitorada.")
    elif umidade is not None and umidade < settings.alerta_umidade_baixa:
        adicionar("umidade_baixa", "warn",
                  "Umidade baixa",
                  f"A umidade está abaixo de {settings.alerta_umidade_baixa:.0f}%. Avalie a necessidade de irrigação.")

    if temperatura is not None and temperatura > settings.alerta_temp_alta:
        adicionar("temp_alta", "warn",
                  f"Temperatura acima de {settings.alerta_temp_alta:.0f}°C",
                  "Calor intenso detectado na leitura mais recente.")
    elif temperatura is not None and temperatura < settings.alerta_temp_baixa:
        adicionar("temp_baixa", "warn",
                  f"Temperatura abaixo de {settings.alerta_temp_baixa:.0f}°C",
                  f"A temperatura está abaixo de {settings.alerta_temp_baixa:.0f}°C.")

    if (
        settings.alerta_solo_seco is not None
        and umidade_solo is not None
        and umidade_solo < settings.alerta_solo_seco
    ):
        adicionar("solo_seco", "warn",
                  "Solo seco",
                  f"Umidade do solo de {umidade_solo:.1f}% está abaixo do limite de {settings.alerta_solo_seco:.1f}%.")

    if (
        temperatura is not None and umidade is not None
        and settings.janela_temp_min <= temperatura <= settings.janela_temp_max
        and settings.janela_umi_min <= umidade <= settings.janela_umi_max
    ):
        adicionar("janela_ideal", "info",
                  "Condições ideais para colheita",
                  "Temperatura e umidade dentro da faixa favorável à colheita.")

    if not alertas:
        adicionar("estavel", "ok",
                  "Condições estáveis",
                  "A última leitura está dentro dos limites monitorados.")

    return alertas


def registrar_historico(db: Session, alertas: list[dict]) -> None:
    """Grava alertas de risco e de janela ideal, uma única vez cada."""
    candidatos = [
        a for a in alertas
        if a["tipo"] == "warn" or a["id"].startswith("janela_ideal-")
    ]
    if not candidatos:
        return

    chaves = [a["id"] for a in candidatos]
    existentes = {
        c for (c,) in db.query(AlertaEmitido.chave).filter(AlertaEmitido.chave.in_(chaves))
    }

    novos = 0
    for a in candidatos:
        if a["id"] in existentes:
            continue
        db.add(AlertaEmitido(
            chave=a["id"],
            tipo=a["tipo"],
            titulo=a["titulo"],
            descricao=a["desc"],
            quando=a["quando"],
        ))
        existentes.add(a["id"])
        novos += 1

    if novos:
        try:
            db.commit()
        except IntegrityError:
            # Outra requisição gravou ao mesmo tempo: não é erro para o usuário
            db.rollback()


def listar_historico(db: Session, limite: int = 50) -> list[dict]:
    linhas = (
        db.query(AlertaEmitido)
        .order_by(AlertaEmitido.id.desc())
        .limit(limite)
        .all()
    )
    return [
        {
            "id": l.chave,
            "tipo": l.tipo,
            "titulo": l.titulo,
            "desc": l.descricao,
            "quando": l.quando,
            "emitido_em": _iso(l.criado_em),
        }
        for l in linhas
    ]