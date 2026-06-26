"""Inicializa FastAPI + pywebview (app desktop local)."""
import sys
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.db import init_db

WEB_DIR = Path(__file__).resolve().parent / "web"

HOST = "127.0.0.1"
PORT = 8756

app = FastAPI(title="Bot de Cobranca")
app.include_router(router)


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


# Arquivos estaticos (styles.css, app.js)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def _run_server():
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def main():
    init_db()

    # Sobe o FastAPI em thread separada
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    try:
        import webview

        webview.create_window(
            "Bot de Cobranca",
            f"http://{HOST}:{PORT}/",
            width=1200,
            height=800,
            min_size=(900, 600),
        )
        webview.start()
    except ImportError:
        print(f"pywebview indisponivel. Acesse http://{HOST}:{PORT}/ no navegador.")
        server_thread.join()


if __name__ == "__main__":
    main()
