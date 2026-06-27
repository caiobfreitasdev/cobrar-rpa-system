"""Inicializa FastAPI + pywebview (app desktop local)."""
import sys
import threading

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import resource_path, set_excel_path, get_excel_path
from app.core.db import init_db

WEB_DIR = resource_path("app", "web")

HOST = "127.0.0.1"
PORT = 8756

app = FastAPI(title="Bot de Cobranca")
app.include_router(router)

# Garante o schema do banco no import (cobre execucao via uvicorn e via exe).
init_db()


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


# Arquivos estaticos (styles.css, app.js)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def _run_server():
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


# Intervalo do agendador (segundos). Enquanto o app esta aberto, verifica
# agendamentos manuais vencidos e aplica a regua automatica.
SCHEDULER_INTERVAL = 60


def _run_scheduler():
    import time

    from app.services import agendamentos

    while True:
        try:
            agendamentos.processar_pendentes()
        except Exception as exc:  # noqa: BLE001
            print(f"[scheduler] erro: {exc}")
        time.sleep(SCHEDULER_INTERVAL)


class JsApi:
    """API nativa exposta ao frontend (file picker do pywebview)."""

    def escolher_planilha(self):
        import webview

        janela = webview.windows[0]
        resultado = janela.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("Planilhas Excel (*.xlsx;*.xls)", "Todos os arquivos (*.*)"),
        )
        if not resultado:
            return {"selecionado": False}
        caminho = resultado[0]
        set_excel_path(caminho)
        return {"selecionado": True, "path": caminho}

    def caminho_atual(self):
        return {"path": get_excel_path()}


def main():
    # Sobe o FastAPI em thread separada
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    # Agendador em background (manuais vencidos + regua automatica)
    scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True)
    scheduler_thread.start()

    try:
        import webview

        webview.create_window(
            "Bot de Cobranca",
            f"http://{HOST}:{PORT}/",
            width=1200,
            height=800,
            min_size=(900, 600),
            js_api=JsApi(),
        )
        webview.start()
    except ImportError:
        print(f"pywebview indisponivel. Acesse http://{HOST}:{PORT}/ no navegador.")
        server_thread.join()


if __name__ == "__main__":
    main()
