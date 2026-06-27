"""Relatorio de cobrancas: consulta de envios e exportacao CSV."""
import csv
import io

from app.core.db import db_session

_ORIGEM_LABEL = {
    "manual": "Individual",
    "lote": "Lote",
    "agendado": "Agendado",
    "regua": "Regua automatica",
}


def listar_envios(status: str = None, limite: int = 1000) -> list[dict]:
    """Lista os envios (mais recentes primeiro) com dados do titulo."""
    where = []
    params: list = []
    if status in ("enviado", "erro"):
        where.append("e.status_envio = ?")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT
            e.id, e.data_envio, e.status_envio, e.origem, e.regra_dias, e.erro,
            t.cliente, t.titulo, t.doc_fiscal, t.email, t.total_atualizado,
            t.vencimento, t.dias_atraso
        FROM envios e
        JOIN titulos t ON t.id = e.titulo_id
        {where_sql}
        ORDER BY e.data_envio DESC
        LIMIT ?
    """
    params.append(limite)
    with db_session() as conn:
        rows = conn.execute(sql, params).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["origem_label"] = _ORIGEM_LABEL.get(d["origem"], d["origem"] or "-")
        result.append(d)
    return result


def resumo_envios() -> dict:
    with db_session() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM envios").fetchone()["c"]
        enviados = conn.execute(
            "SELECT COUNT(*) c FROM envios WHERE status_envio = 'enviado'"
        ).fetchone()["c"]
        erros = conn.execute(
            "SELECT COUNT(*) c FROM envios WHERE status_envio = 'erro'"
        ).fetchone()["c"]
    return {"total": total, "enviados": enviados, "erros": erros}


def exportar_csv(status: str = None) -> str:
    """Gera o conteudo CSV (string) do relatorio de envios."""
    envios = listar_envios(status=status, limite=100000)
    buffer = io.StringIO()
    # ; como separador e BOM ajudam o Excel pt-BR a abrir corretamente
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([
        "Data do Envio", "Status", "Origem", "Regra (dias)", "Cliente",
        "Titulo", "Doc. Fiscal", "E-mail", "Total Atualizado",
        "Vencimento", "Dias de Atraso", "Erro",
    ])
    for e in envios:
        writer.writerow([
            e["data_envio"], e["status_envio"], e["origem_label"],
            e["regra_dias"] if e["regra_dias"] is not None else "",
            e["cliente"], e["titulo"], e["doc_fiscal"], e["email"],
            f'{e["total_atualizado"]:.2f}'.replace(".", ",") if e["total_atualizado"] is not None else "",
            e["vencimento"], e["dias_atraso"], e["erro"] or "",
        ])
    return "﻿" + buffer.getvalue()
