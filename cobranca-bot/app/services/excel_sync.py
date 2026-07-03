"""Le as abas BASE e INADIMPLENCIA do Excel, cruza status e faz upsert no SQLite."""
import hashlib
import unicodedata
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from app.core.config import get_excel_path
from app.core.db import db_session, agora_local

SHEET_NAME = "BASE"
# Aba com o STATUS por cliente (COBRANCA / NEGATIVADO / JURIDICO...).
# O envio so e liberado para clientes listados nela com status permitido.
SHEET_STATUS = "INADIMPLENCIA"

# Mapeia colunas do Excel -> campos do banco.
# Colunas opcionais (Email, Link de Cobranca) sao tratadas separadamente.
COLUMN_MAP = {
    "UF": "uf",
    "Cd.Cliente": "cd_cliente",
    "Cliente": "cliente",
    "Título": "titulo",
    "Doc.Fiscal": "doc_fiscal",
    "Vl.Título": "vl_titulo",
    "Juros": "juros",
    "Multa": "multa",
    "Total Atualizado": "total_atualizado",
    "Emissão": "emissao",
    "Vencimento": "vencimento",
    "OBS": "obs",
    "Dias de Atraso": "dias_atraso",
}

# Campos que entram no hash para detectar alteracao relevante.
# dias_atraso NAO entra: muda todo dia na planilha e e calculado
# internamente a partir do vencimento (senao toda carga marcaria
# todos os titulos como "alterados").
HASH_FIELDS = [
    "vl_titulo", "juros", "multa", "total_atualizado",
    "vencimento", "email", "link_cobranca", "status_cliente",
]


def normalizar_nome(valor: Any) -> str:
    """Normaliza para cruzamento por nome: maiusculas, sem acentos,
    espacos colapsados. Nao remove sufixos (LTDA etc.) para evitar
    falsos positivos entre empresas parecidas."""
    s = str(valor or "").strip().upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def _carregar_status_clientes(caminho: str) -> Optional[dict]:
    """Le a aba INADIMPLENCIA e retorna {nome_normalizado: STATUS}.

    O cabecalho nao esta na primeira linha: e localizado dinamicamente
    pela linha que contem CLIENTES e STATUS. Retorna None se a aba
    nao existir (a carga segue, mas nada fica liberado para envio).
    """
    xls = pd.ExcelFile(caminho, engine="openpyxl")
    aba = next((s for s in xls.sheet_names
                if normalizar_nome(s) == SHEET_STATUS), None)
    if aba is None:
        return None

    bruto = pd.read_excel(caminho, sheet_name=aba, engine="openpyxl", header=None)
    col_cliente = col_status = linha_hdr = None
    for i in range(min(10, len(bruto))):  # cabecalho nas primeiras linhas
        valores = [normalizar_nome(v) for v in bruto.iloc[i]]
        if "CLIENTES" in valores and "STATUS" in valores:
            linha_hdr = i
            col_cliente = valores.index("CLIENTES")
            col_status = valores.index("STATUS")
            break
    if linha_hdr is None:
        return None

    mapa: dict = {}
    for _, row in bruto.iloc[linha_hdr + 1:].iterrows():
        nome = normalizar_nome(row.iloc[col_cliente])
        status = normalizar_nome(row.iloc[col_status])
        if nome and nome != "NAN" and status and status != "NAN":
            mapa[nome] = status
    return mapa


def _clean_str(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if pd.isna(value):
        return None
    texto = str(value).strip()
    return texto or None


def _clean_float(value: Any) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_int(value: Any) -> Optional[int]:
    f = _clean_float(value)
    return int(f) if f is not None else None


def _clean_date(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%Y-%m-%d")
    # Tenta parsear string: primeiro ISO (YYYY-MM-DD), depois formato BR (dd/mm/aaaa)
    texto = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return pd.to_datetime(texto, dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return _clean_str(value)


def _compute_hash(record: dict) -> str:
    parts = [str(record.get(f) or "") for f in HASH_FIELDS]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _row_to_record(row: pd.Series, has_email: bool, has_link: bool,
                   status_map: Optional[dict] = None) -> dict:
    rec: dict = {}
    for excel_col, db_field in COLUMN_MAP.items():
        rec[db_field] = row.get(excel_col)

    # Limpeza por tipo
    rec["uf"] = _clean_str(rec["uf"])
    rec["cd_cliente"] = _clean_str(rec["cd_cliente"])
    rec["cliente"] = _clean_str(rec["cliente"])
    rec["titulo"] = _clean_str(rec["titulo"])
    rec["doc_fiscal"] = _clean_str(rec["doc_fiscal"])
    rec["vl_titulo"] = _clean_float(rec["vl_titulo"])
    rec["juros"] = _clean_float(rec["juros"])
    rec["multa"] = _clean_float(rec["multa"])
    rec["total_atualizado"] = _clean_float(rec["total_atualizado"])
    rec["emissao"] = _clean_date(rec["emissao"])
    rec["vencimento"] = _clean_date(rec["vencimento"])
    rec["obs"] = _clean_str(rec["obs"])
    rec["dias_atraso"] = _clean_int(rec["dias_atraso"])

    # Colunas novas em construcao: lidas se existirem, senao vazias.
    rec["email"] = _clean_str(row.get("Email")) if has_email else None
    rec["link_cobranca"] = _clean_str(row.get("Link de Cobrança")) if has_link else None

    # Cruzamento por nome com a aba INADIMPLENCIA (status do cliente).
    rec["status_cliente"] = (status_map or {}).get(normalizar_nome(rec["cliente"]))

    rec["hash_linha"] = _compute_hash(rec)
    return rec


def load_dataframe() -> pd.DataFrame:
    caminho = get_excel_path()
    if not caminho:
        raise ValueError("Nenhuma planilha selecionada. Use 'Selecionar planilha'.")
    df = pd.read_excel(caminho, sheet_name=SHEET_NAME, engine="openpyxl")
    # Tolera espacos extras nos cabecalhos ("Total  Atualizado", "Juros ").
    df.columns = [" ".join(str(c).split()) for c in df.columns]
    return df


def sync() -> dict:
    """Executa a sincronizacao completa. Retorna resumo da carga."""
    df = load_dataframe()
    status_map = _carregar_status_clientes(get_excel_path())

    has_email = "Email" in df.columns
    has_link = "Link de Cobrança" in df.columns

    records = []
    for _, row in df.iterrows():
        rec = _row_to_record(row, has_email, has_link, status_map)
        # Ignora linhas sem chave de negocio
        if not rec["cd_cliente"] or not rec["titulo"]:
            continue
        records.append(rec)

    novos = 0
    alterados = 0
    baixados = 0
    chaves_carga = set()

    with db_session() as conn:
        for rec in records:
            chave = (rec["cd_cliente"], rec["titulo"])
            chaves_carga.add(chave)

            existing = conn.execute(
                "SELECT id, hash_linha FROM titulos WHERE cd_cliente = ? AND titulo = ?",
                (rec["cd_cliente"], rec["titulo"]),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO titulos
                    (uf, cd_cliente, cliente, email, titulo, doc_fiscal, vl_titulo,
                     juros, multa, total_atualizado, emissao, vencimento, dias_atraso,
                     obs, link_cobranca, status_cliente, hash_linha, ativo,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        rec["uf"], rec["cd_cliente"], rec["cliente"], rec["email"],
                        rec["titulo"], rec["doc_fiscal"], rec["vl_titulo"], rec["juros"],
                        rec["multa"], rec["total_atualizado"], rec["emissao"],
                        rec["vencimento"], rec["dias_atraso"], rec["obs"],
                        rec["link_cobranca"], rec["status_cliente"], rec["hash_linha"],
                        agora_local(), agora_local(),
                    ),
                )
                novos += 1
            elif existing["hash_linha"] != rec["hash_linha"]:
                conn.execute(
                    """
                    UPDATE titulos SET
                        uf = ?, cliente = ?, email = ?, doc_fiscal = ?, vl_titulo = ?,
                        juros = ?, multa = ?, total_atualizado = ?, emissao = ?,
                        vencimento = ?, dias_atraso = ?, obs = ?, link_cobranca = ?,
                        status_cliente = ?, hash_linha = ?, ativo = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        rec["uf"], rec["cliente"], rec["email"], rec["doc_fiscal"],
                        rec["vl_titulo"], rec["juros"], rec["multa"],
                        rec["total_atualizado"], rec["emissao"], rec["vencimento"],
                        rec["dias_atraso"], rec["obs"], rec["link_cobranca"],
                        rec["status_cliente"], rec["hash_linha"], agora_local(),
                        existing["id"],
                    ),
                )
                alterados += 1
            else:
                # Mesmo hash: garante que esta marcado como ativo (pode ter voltado)
                conn.execute(
                    "UPDATE titulos SET ativo = 1 WHERE id = ?", (existing["id"],)
                )

        # Marca como inativos (provavel pagamento) os que nao vieram na carga
        ativos = conn.execute(
            "SELECT id, cd_cliente, titulo FROM titulos WHERE ativo = 1"
        ).fetchall()
        for t in ativos:
            if (t["cd_cliente"], t["titulo"]) not in chaves_carga:
                conn.execute(
                    "UPDATE titulos SET ativo = 0, updated_at = ? WHERE id = ?",
                    (agora_local(), t["id"]),
                )
                baixados += 1

    liberados = sum(1 for r in records
                    if r["status_cliente"] in ("COBRANCA", "NEGATIVADO"))
    return {
        "novos": novos,
        "alterados": alterados,
        "baixados": baixados,
        "total_carga": len(records),
        "email_disponivel": has_email,
        "link_disponivel": has_link,
        "status_disponivel": status_map is not None,
        "titulos_liberados": liberados,
        "titulos_bloqueados": len(records) - liberados,
    }
