"""Render do template HTML, envio SMTP e log em 'envios'."""
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings, resource_path
from app.core.db import db_session
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


def _enviar_smtp(destinatario: str, assunto: str, corpo_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = settings.SMTP_FROM
    msg["To"] = destinatario
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
        server.ehlo()
        try:
            server.starttls()
            server.ehlo()
        except smtplib.SMTPException:
            pass  # servidor pode nao suportar STARTTLS
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [destinatario], msg.as_string())


def _log_envio(titulo_id: int, status: str, erro: str = None) -> None:
    with db_session() as conn:
        conn.execute(
            """INSERT INTO envios (titulo_id, status_envio, canal, erro)
               VALUES (?, ?, 'email', ?)""",
            (titulo_id, status, erro),
        )


def enviar_lote(titulo_ids: list[int]) -> dict:
    """Envia um e-mail por titulo selecionado. Valida e-mail antes de enviar."""
    titulos = buscar_por_ids(titulo_ids)
    enviados = []
    falhas = []
    pendentes = []  # sem e-mail ou bloqueados por regra

    smtp_ok = settings.smtp_configured()

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

        if not smtp_ok:
            falhas.append({"id": t["id"], "cliente": t["cliente"], "erro": "SMTP nao configurado"})
            _log_envio(t["id"], "erro", "SMTP nao configurado")
            continue

        try:
            corpo = render_email(t)
            assunto = f"Cobranca - Titulo {t.get('titulo')}"
            _enviar_smtp(email, assunto, corpo)
            _log_envio(t["id"], "enviado")
            enviados.append({"id": t["id"], "cliente": t["cliente"], "email": email})
        except Exception as exc:  # noqa: BLE001
            _log_envio(t["id"], "erro", str(exc))
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
