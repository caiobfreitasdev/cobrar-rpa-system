"""Render do template HTML, envio via Microsoft Graph e log em 'envios'."""
import re

from app.core.config import settings, resource_path
from app.core.db import db_session, agora_local
from app.services import graph_client
from app.services.titulos import buscar_por_ids
from app.rules import pendencias

TEMPLATE_PATH = resource_path("app", "templates", "email_cobranca.html")

# Bloco condicional do link de pagamento, delimitado por marcadores no template:
#   {% if link_cobranca %} ... {% endif %}
_LINK_BLOCK_RE = re.compile(
    r"\{%\s*if\s+link_cobranca\s*%\}(.*?)\{%\s*endif\s*%\}", re.DOTALL
)


def _format_moeda(valor) -> str:
    if valor is None:
        return "-"
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor)


def _format_data(valor) -> str:
    if not valor:
        return "-"
    # Espera YYYY-MM-DD
    try:
        ano, mes, dia = str(valor).split("-")
        return f"{dia}/{mes}/{ano}"
    except ValueError:
        return str(valor)


def render_email(titulo: dict) -> str:
    html = TEMPLATE_PATH.read_text(encoding="utf-8")

    link = titulo.get("link_cobranca")

    # Resolve bloco condicional do link
    if link:
        html = _LINK_BLOCK_RE.sub(lambda m: m.group(1), html)
    else:
        html = _LINK_BLOCK_RE.sub("", html)

    valores = {
        "cliente": titulo.get("cliente") or "",
        "titulo": titulo.get("titulo") or "",
        "doc_fiscal": titulo.get("doc_fiscal") or "",
        "total_atualizado": _format_moeda(titulo.get("total_atualizado")),
        "vencimento": _format_data(titulo.get("vencimento")),
        "dias_atraso": str(titulo.get("dias_atraso") if titulo.get("dias_atraso") is not None else "-"),
        "link_cobranca": link or "",
    }

    for chave, valor in valores.items():
        html = html.replace("{{" + chave + "}}", valor)
        html = html.replace("{{ " + chave + " }}", valor)

    return html


def _log_envio(titulo_id: int, status: str, erro: str = None,
               origem: str = "manual", regra_dias: int = None) -> None:
    with db_session() as conn:
        conn.execute(
            """INSERT INTO envios (titulo_id, data_envio, status_envio, canal, origem, regra_dias, erro)
               VALUES (?, ?, ?, 'email', ?, ?, ?)""",
            (titulo_id, agora_local(), status, origem, regra_dias, erro),
        )


def enviar_lote(titulo_ids: list[int], origem: str = "manual",
                regra_dias: int = None) -> dict:
    """Envia um e-mail por titulo selecionado. Valida e-mail antes de enviar.

    origem: manual | lote | agendado | regua (registrado no log de envios).
    """
    titulos = buscar_por_ids(titulo_ids)
    enviados = []
    falhas = []
    pendentes = []  # sem e-mail ou bloqueados por regra

    graph_ok = settings.graph_configured()

    for t in titulos:
        # Gancho das regras pendentes (flags desligadas nesta fase).
        bloqueio = pendencias.bloquear_envio(t)
        if bloqueio:
            pendentes.append({"id": t["id"], "cliente": t["cliente"], "motivo": bloqueio})
            continue

        email = (t.get("email") or "").strip()
        if not email:
            pendentes.append({"id": t["id"], "cliente": t["cliente"], "motivo": "sem e-mail"})
            continue

        if not graph_ok:
            falhas.append({"id": t["id"], "cliente": t["cliente"], "erro": "Graph nao configurado"})
            _log_envio(t["id"], "erro", "Graph nao configurado", origem, regra_dias)
            continue

        try:
            corpo = render_email(t)
            assunto = f"Notificação de Débito – Título {t.get('titulo')}"
            graph_client.enviar_email(email, assunto, corpo)
            _log_envio(t["id"], "enviado", None, origem, regra_dias)
            enviados.append({"id": t["id"], "cliente": t["cliente"], "email": email})
        except Exception as exc:  # noqa: BLE001
            _log_envio(t["id"], "erro", str(exc), origem, regra_dias)
            falhas.append({"id": t["id"], "cliente": t["cliente"], "erro": str(exc)})

    return {
        "enviados": enviados,
        "falhas": falhas,
        "pendentes": pendentes,
        "total_enviados": len(enviados),
        "total_falhas": len(falhas),
        "total_pendentes": len(pendentes),
    }


def preview_lote(titulo_ids: list[int]) -> dict:
    """Resumo para confirmacao antes do envio real."""
    titulos = buscar_por_ids(titulo_ids)
    com_email = [t for t in titulos if (t.get("email") or "").strip()]
    sem_email = [t for t in titulos if not (t.get("email") or "").strip()]
    return {
        "total": len(titulos),
        "com_email": len(com_email),
        "sem_email": len(sem_email),
        "itens": [
            {
                "id": t["id"],
                "cliente": t["cliente"],
                "titulo": t["titulo"],
                "email": t.get("email") or "",
                "total_atualizado": t.get("total_atualizado"),
            }
            for t in titulos
        ],
    }
