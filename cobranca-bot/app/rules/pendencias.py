"""Regras de negocio pendentes para producao.

Nesta fase TODAS as flags estao DESLIGADAS e nao tem efeito no envio.
O envio segue sempre manual, com confirmacao explicita de lote.
"""
from typing import Optional

# ---------------------------------------------------------------------------
# FLAGS (todas desligadas nesta fase)
# ---------------------------------------------------------------------------

# TODO: Quando ativada, bloquear envio para clientes com STATUS
#       JURIDICO / NEGATIVADO / ACORDO.
#       A coluna STATUS ainda NAO existe na aba BASE. Quando ela existir,
#       carregar o campo em titulos e implementar a checagem em
#       bloquear_envio() abaixo.
TRAVA_STATUS = False

# TODO: Regua de cobranca automatica por dias de atraso.
#       Por enquanto NAO ha automacao: o operador seleciona e confirma o lote.
REGUA_AUTOMATICA = False


# Status que, quando a TRAVA_STATUS estiver ligada, bloqueiam o envio.
STATUS_BLOQUEADOS = {"JURIDICO", "NEGATIVADO", "ACORDO"}


def bloquear_envio(titulo: dict) -> Optional[str]:
    """Retorna o motivo do bloqueio, ou None se o envio esta liberado.

    Gancho pronto para a TRAVA_STATUS. Como a flag esta desligada e a coluna
    STATUS ainda nao existe, sempre retorna None nesta fase.
    """
    if TRAVA_STATUS:
        status = (titulo.get("status") or "").strip().upper()
        if status in STATUS_BLOQUEADOS:
            return f"bloqueado por STATUS={status}"
    return None


def pendencias_producao() -> list[dict]:
    """Lista as pendencias a resolver antes de ir para producao (para o dashboard)."""
    return [
        {
            "chave": "TRAVA_STATUS",
            "ativa": TRAVA_STATUS,
            "titulo": "Trava de STATUS",
            "descricao": (
                "Bloquear envio para clientes JURIDICO / NEGATIVADO / ACORDO. "
                "Coluna STATUS ainda nao existe na aba BASE."
            ),
        },
        {
            "chave": "TRAVA_LINK",
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
        {
            "chave": "COLUNA_EMAIL",
            "ativa": False,
            "titulo": "Coluna de Email na BASE",
            "descricao": (
                "Coluna 'Email' em construcao ao lado de 'Cliente'. Lida se existir; "
                "sem ela, envios ficam pendentes por falta de e-mail."
            ),
        },
    ]
