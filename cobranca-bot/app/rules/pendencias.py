"""Regras de negocio do envio.

TRAVA_STATUS (ATIVA): lista fechada por cliente, vinda da aba INADIMPLENCIA
da planilha (cruzamento por nome). So recebem cobranca os clientes com
status permitido; quem nao esta na aba (ou esta com outro status, ex:
JURIDICO) fica bloqueado e oculto do dashboard.
"""
from typing import Optional

# Lista fechada: somente estes status liberam o envio.
TRAVA_STATUS = True
STATUS_PERMITIDOS = {"COBRANCA", "NEGATIVADO"}


def envio_liberado(titulo: dict) -> bool:
    """True se o cliente do titulo esta liberado para cobranca."""
    status = (titulo.get("status_cliente") or "").strip().upper()
    return status in STATUS_PERMITIDOS


def bloquear_envio(titulo: dict) -> Optional[str]:
    """Retorna o motivo do bloqueio, ou None se o envio esta liberado."""
    if not TRAVA_STATUS:
        return None
    if envio_liberado(titulo):
        return None
    status = (titulo.get("status_cliente") or "").strip().upper()
    if status:
        return f"bloqueado por STATUS={status}"
    return "cliente fora da aba INADIMPLENCIA (sem status)"


def pendencias_producao() -> list[dict]:
    """Lista as pendencias tecnicas (painel recolhivel do dashboard)."""
    return [
        {
            "chave": "TRAVA_STATUS",
            "ativa": TRAVA_STATUS,
            "titulo": "Trava de STATUS (ativa)",
            "descricao": (
                "Lista fechada pela aba INADIMPLENCIA: so recebem cobranca "
                "clientes com status COBRANCA ou NEGATIVADO. Demais ficam "
                "ocultos e bloqueados."
            ),
        },
        {
            "chave": "SECRET_AZURE",
            "ativa": False,
            "titulo": "Conferir secret do Azure (expira)",
            "descricao": (
                "O client secret do Graph tem validade. Anote a data de expiracao "
                "e renove no Azure antes de vencer para nao parar os envios."
            ),
        },
        {
            "chave": "LINK_COBRANCA",
            "ativa": False,
            "titulo": "Integracao do link de cobranca (cartao)",
            "descricao": (
                "Coluna 'Link de Cobranca' em construcao. So o campo/placeholder "
                "esta pronto; a validacao do link real virá depois."
            ),
        },
    ]
