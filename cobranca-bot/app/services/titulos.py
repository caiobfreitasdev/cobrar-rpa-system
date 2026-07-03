"""Consultas de titulos para o dashboard."""
from typing import Optional

from app.core.db import db_session

# Dias de atraso calculados internamente (hoje - vencimento), sempre atuais
# mesmo sem recarregar a planilha. Fallback para o valor da planilha quando
# nao ha vencimento. Nunca negativo (titulo a vencer = 0).
DIAS_ATRASO_SQL = (
    "COALESCE(MAX(0, CAST(julianday(date('now','localtime')) "
    "- julianday(t.vencimento) AS INTEGER)), t.dias_atraso)"
)


def listar_titulos(
    apenas_ativos: bool = True,
    status_envio: Optional[str] = None,
    ordenar_por_atraso: bool = True,
) -> list[dict]:
    """Lista titulos com status de cobranca (ultimo envio bem-sucedido)."""
    where = []
    params: list = []
    if apenas_ativos:
        where.append("t.ativo = 1")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_sql = f"ORDER BY {DIAS_ATRASO_SQL} DESC" if ordenar_por_atraso else "ORDER BY t.cliente"

    sql = f"""
        SELECT
            t.id, t.uf, t.cd_cliente, t.cliente, t.email, t.titulo,
            t.doc_fiscal, t.vl_titulo, t.juros, t.multa, t.total_atualizado,
            t.emissao, t.vencimento, {DIAS_ATRASO_SQL} AS dias_atraso,
            t.obs, t.link_cobranca, t.ativo,
            (SELECT MAX(e.data_envio) FROM envios e
                WHERE e.titulo_id = t.id AND e.status_envio = 'enviado') AS ultimo_envio
        FROM titulos t
        {where_sql}
        {order_sql}
    """
    with db_session() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["cobrado"] = d["ultimo_envio"] is not None
        result.append(d)

    # Filtro por status de envio em Python (depende do calculo de cobrado)
    if status_envio == "cobrado":
        result = [d for d in result if d["cobrado"]]
    elif status_envio == "nao_cobrado":
        result = [d for d in result if not d["cobrado"]]

    return result


def buscar_por_ids(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    sql = f"""SELECT t.*, {DIAS_ATRASO_SQL} AS dias_atraso_calc
              FROM titulos t WHERE t.id IN ({placeholders})"""
    with db_session() as conn:
        rows = conn.execute(sql, ids).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["dias_atraso"] = d.pop("dias_atraso_calc")
        result.append(d)
    return result


def resumo_geral() -> dict:
    with db_session() as conn:
        total_ativos = conn.execute(
            "SELECT COUNT(*) c FROM titulos WHERE ativo = 1"
        ).fetchone()["c"]
        cobrados = conn.execute(
            """
            SELECT COUNT(DISTINCT t.id) c FROM titulos t
            JOIN envios e ON e.titulo_id = t.id AND e.status_envio = 'enviado'
            WHERE t.ativo = 1
            """
        ).fetchone()["c"]
    return {
        "total_ativos": total_ativos,
        "cobrados": cobrados,
        "nao_cobrados": total_ativos - cobrados,
    }
