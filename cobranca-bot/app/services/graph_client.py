"""Cliente do Microsoft Graph API para envio de e-mail.

Fluxo client credentials (app-only):
  1. Obtem token em login.microsoftonline.com/{tenant}/oauth2/v2.0/token
  2. Envia e-mail via POST /users/{sender}/sendMail

Pre-requisito no Azure: o App Registration precisa da permissao de
APLICACAO Mail.Send (com consentimento de admin concedido).
"""
import time

import requests

from app.core.config import settings

_AUTHORITY = "https://login.microsoftonline.com"
_GRAPH = "https://graph.microsoft.com/v1.0"
_SCOPE = "https://graph.microsoft.com/.default"

# Cache simples do token em memoria (renovado antes de expirar).
_token_cache = {"value": None, "exp": 0.0}


def _now() -> float:
    return time.time()


def obter_token(forcar: bool = False) -> str:
    """Retorna um access_token valido, usando cache enquanto nao expira."""
    if not forcar and _token_cache["value"] and _now() < _token_cache["exp"] - 120:
        return _token_cache["value"]

    if not settings.graph_configured():
        raise RuntimeError("Credenciais do Graph nao configuradas no .env")

    url = f"{_AUTHORITY}/{settings.GRAPH_TENANT}/oauth2/v2.0/token"
    data = {
        "client_id": settings.GRAPH_CLIENT_ID,
        "client_secret": settings.GRAPH_CLIENT_SECRET,
        "scope": _SCOPE,
        "grant_type": "client_credentials",
    }
    resp = requests.post(url, data=data, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Falha ao obter token ({resp.status_code}): {resp.text[:300]}")

    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Token nao retornado pelo Azure AD")

    _token_cache["value"] = token
    _token_cache["exp"] = _now() + float(payload.get("expires_in", 3600))
    return token


def enviar_email(destinatario: str, assunto: str, corpo_html: str) -> None:
    """Envia um e-mail HTML pela caixa GRAPH_SENDER. Lanca em caso de erro."""
    token = obter_token()
    url = f"{_GRAPH}/users/{settings.GRAPH_SENDER}/sendMail"
    body = {
        "message": {
            "subject": assunto,
            "body": {"contentType": "HTML", "content": corpo_html},
            "toRecipients": [{"emailAddress": {"address": destinatario}}],
        },
        "saveToSentItems": True,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json=body, headers=headers, timeout=30)
    # sendMail retorna 202 Accepted em caso de sucesso.
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"Graph sendMail {resp.status_code}: {resp.text[:300]}")


def testar_conexao() -> dict:
    """Valida credenciais obtendo um token (sem enviar e-mail)."""
    try:
        obter_token(forcar=True)
        return {"ok": True, "mensagem": "Token obtido com sucesso. Credenciais validas."}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "mensagem": str(exc)}
