"""Agendamento de cobrancas: manual (data/hora) e regua automatica.

O agendador (scheduler) chama processar_pendentes() periodicamente enquanto
o app esta aberto. Dois mecanismos:

- Manual: registros na tabela 'agendamentos' com data_agendada. Quando a hora
  chega, o lote correspondente e enviado.
- Regua automatica: para cada titulo ativo com e-mail, ao atingir um marco de
  dias de atraso (ex: 7, 15, 30), envia uma vez por marco (dedup via envios).
"""
from datetime import datetime

from app.core.config import get_regua
from app.core.db import db_session
from app.services import email_sender


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Agendamento manual
# ---------------------------------------------------------------------------
def criar_agendamentos(titulo_ids: list[int], data_agendada: str) -> dict:
    """Cria um agendamento por titulo para a data/hora informada.

    data_agendada: 'YYYY-MM-DD HH:MM' ou ISO equivalente.
    """
    # normaliza a entrada do <input type=datetime-local> ('YYYY-MM-DDTHH:MM')
    dt = data_agendada.replace("T", " ")
    if len(dt) == 16:  # sem segundos
        dt += ":00"
    try:
        datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise ValueError("Data/hora invalida")

    criados = 0
    with db_session() as conn:
        for tid in titulo_ids:
            conn.execute(
                "INSERT INTO agendamentos (titulo_id, data_agendada, status) VALUES (?, ?, 'pendente')",
                (tid, dt),
            )
            criados += 1
    return {"criados": criados, "data_agendada": dt}


def listar_agendamentos(status: str = None) -> list[dict]:
    where = "WHERE a.status = ?" if status else ""
    params = [status] if status else []
    sql = f"""
        SELECT a.id, a.titulo_id, a.data_agendada, a.status, a.erro,
               a.executado_em, t.cliente, t.titulo, t.email, t.total_atualizado
        FROM agendamentos a
        JOIN titulos t ON t.id = a.titulo_id
        {where}
        ORDER BY a.data_agendada ASC
    """
    with db_session() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def cancelar(agendamento_id: int) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE agendamentos SET status = 'cancelado' WHERE id = ? AND status = 'pendente'",
            (agendamento_id,),
        )


# ---------------------------------------------------------------------------
# Processamento (chamado pelo scheduler)
# ---------------------------------------------------------------------------
def _processar_manuais() -> int:
    """Dispara agendamentos manuais cuja hora ja chegou. Retorna qtos enviados."""
    agora = _agora()
    with db_session() as conn:
        vencidos = conn.execute(
            "SELECT id, titulo_id FROM agendamentos WHERE status = 'pendente' AND data_agendada <= ?",
            (agora,),
        ).fetchall()

    enviados = 0
    for ag in vencidos:
        res = email_sender.enviar_lote([ag["titulo_id"]], origem="agendado")
        ok = res["total_enviados"] > 0
        with db_session() as conn:
            if ok:
                conn.execute(
                    "UPDATE agendamentos SET status='executado', executado_em=? WHERE id=?",
                    (_agora(), ag["id"]),
                )
                enviados += 1
            else:
                motivo = (res["falhas"] or res["pendentes"] or [{}])[0]
                erro = motivo.get("erro") or motivo.get("motivo") or "nao enviado"
                conn.execute(
                    "UPDATE agendamentos SET status='erro', erro=?, executado_em=? WHERE id=?",
                    (erro, _agora(), ag["id"]),
                )
    return enviados


def _ja_enviado_na_regra(titulo_id: int, regra_dias: int) -> bool:
    with db_session() as conn:
        row = conn.execute(
            """SELECT 1 FROM envios
               WHERE titulo_id = ? AND status_envio = 'enviado'
                 AND origem = 'regua' AND regra_dias = ? LIMIT 1""",
            (titulo_id, regra_dias),
        ).fetchone()
    return row is not None


def _processar_regua() -> int:
    """Aplica a regua automatica. Envia uma vez por marco de dias de atraso."""
    cfg = get_regua()
    if not cfg["ativa"] or not cfg["dias"]:
        return 0

    with db_session() as conn:
        titulos = conn.execute(
            """SELECT id, dias_atraso, email FROM titulos
               WHERE ativo = 1 AND email IS NOT NULL AND TRIM(email) <> ''"""
        ).fetchall()

    enviados = 0
    marcos = sorted(cfg["dias"])
    for t in titulos:
        atraso = t["dias_atraso"] or 0
        # maior marco ja atingido pelo atraso atual
        aplicaveis = [d for d in marcos if atraso >= d]
        if not aplicaveis:
            continue
        marco = aplicaveis[-1]
        if _ja_enviado_na_regra(t["id"], marco):
            continue
        res = email_sender.enviar_lote([t["id"]], origem="regua", regra_dias=marco)
        if res["total_enviados"] > 0:
            enviados += 1
    return enviados


def processar_pendentes() -> dict:
    """Tick do agendador: manuais vencidos + regua. Retorna resumo."""
    manuais = _processar_manuais()
    regua = _processar_regua()
    return {"manuais_enviados": manuais, "regua_enviados": regua}
