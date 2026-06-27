"""Endpoints FastAPI."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import settings, get_excel_path, get_regua, set_regua
from app.rules import pendencias
from app.services import (
    agendamentos as agend_svc,
    excel_sync,
    email_sender,
    graph_client,
    relatorios,
    titulos as titulos_svc,
)

router = APIRouter(prefix="/api")

# Guarda o resumo da ultima carga em memoria para exibir no dashboard.
_ultima_carga: dict = {}


class LoteRequest(BaseModel):
    titulo_ids: list[int]
    origem: str = "manual"


class AgendarRequest(BaseModel):
    titulo_ids: list[int]
    data_agendada: str


class ReguaRequest(BaseModel):
    ativa: bool
    dias: list[int]


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
        "excel_path": get_excel_path(),
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
    origem = "lote" if len(req.titulo_ids) > 1 else "manual"
    return email_sender.enviar_lote(req.titulo_ids, origem=origem)


# ---------------------------------------------------------------------------
# Relatorio de cobrancas
# ---------------------------------------------------------------------------
@router.get("/relatorio")
def get_relatorio(status: str | None = None):
    return {
        "resumo": relatorios.resumo_envios(),
        "envios": relatorios.listar_envios(status=status),
    }


@router.get("/relatorio/export")
def get_relatorio_export(status: str | None = None):
    conteudo = relatorios.exportar_csv(status=status)
    return Response(
        content=conteudo.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=relatorio_cobrancas.csv"},
    )


# ---------------------------------------------------------------------------
# Agendamento
# ---------------------------------------------------------------------------
@router.get("/agendamentos")
def get_agendamentos(status: str | None = None):
    return agend_svc.listar_agendamentos(status=status)


@router.post("/agendamentos")
def post_agendamentos(req: AgendarRequest):
    if not req.titulo_ids:
        raise HTTPException(400, "Nenhum titulo selecionado")
    try:
        return agend_svc.criar_agendamentos(req.titulo_ids, req.data_agendada)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/agendamentos/{agendamento_id}/cancelar")
def post_cancelar_agendamento(agendamento_id: int):
    agend_svc.cancelar(agendamento_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Regua automatica
# ---------------------------------------------------------------------------
@router.get("/regua")
def get_regua_cfg():
    return get_regua()


@router.post("/regua")
def post_regua_cfg(req: ReguaRequest):
    set_regua(req.ativa, req.dias)
    return get_regua()
