"""Endpoints FastAPI."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.rules import pendencias
from app.services import excel_sync, email_sender, graph_client, titulos as titulos_svc

router = APIRouter(prefix="/api")

# Guarda o resumo da ultima carga em memoria para exibir no dashboard.
_ultima_carga: dict = {}


class LoteRequest(BaseModel):
    titulo_ids: list[int]


@router.get("/titulos")
def get_titulos(status: str | None = None, ordenar_atraso: bool = True):
    return titulos_svc.listar_titulos(
        apenas_ativos=True,
        status_envio=status,
        ordenar_por_atraso=ordenar_atraso,
    )


@router.get("/resumo")
def get_resumo():
    return {
        "geral": titulos_svc.resumo_geral(),
        "ultima_carga": _ultima_carga,
        "graph_configurado": settings.graph_configured(),
        "graph_sender": settings.GRAPH_SENDER,
        "excel_path": settings.EXCEL_PATH,
    }


@router.post("/graph/test")
def post_graph_test():
    """Valida as credenciais do Graph obtendo um token (nao envia e-mail)."""
    return graph_client.testar_conexao()


@router.get("/pendencias")
def get_pendencias():
    return pendencias.pendencias_producao()


@router.post("/sync")
def post_sync():
    global _ultima_carga
    try:
        resumo = excel_sync.sync()
    except FileNotFoundError:
        raise HTTPException(404, "Arquivo Excel nao encontrado. Verifique EXCEL_PATH no .env")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Erro ao sincronizar: {exc}")
    _ultima_carga = resumo
    return resumo


@router.post("/lote/preview")
def post_preview(req: LoteRequest):
    if not req.titulo_ids:
        raise HTTPException(400, "Nenhum titulo selecionado")
    return email_sender.preview_lote(req.titulo_ids)


@router.post("/lote/enviar")
def post_enviar(req: LoteRequest):
    if not req.titulo_ids:
        raise HTTPException(400, "Nenhum titulo selecionado")
    return email_sender.enviar_lote(req.titulo_ids)
