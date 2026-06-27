"""Carrega configuracoes do .env. Nunca hardcode credenciais."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _base_dir() -> Path:
    """Diretorio base da aplicacao (compativel com PyInstaller)."""
    if getattr(sys, "frozen", False):
        # Rodando como .exe empacotado pelo PyInstaller
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


BASE_DIR = _base_dir()


def resource_path(*parts: str) -> Path:
    """Resolve caminho de recursos empacotados (templates, web).

    No exe (PyInstaller onefile) os dados ficam em sys._MEIPASS; em
    desenvolvimento, na raiz do projeto.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", BASE_DIR))
    else:
        base = Path(__file__).resolve().parents[2]
    return base.joinpath(*parts)

# Procura o .env ao lado do executavel/projeto
load_dotenv(BASE_DIR / ".env")


class Settings:
    EXCEL_PATH: str = os.getenv("EXCEL_PATH", "")

    # Microsoft Graph API (envio de e-mail via client credentials)
    GRAPH_CLIENT_ID: str = os.getenv("ID_CLIENT_ID", "")
    GRAPH_CLIENT_SECRET: str = os.getenv("ID_CLIENT_SECRET", "")
    GRAPH_TENANT: str = os.getenv("ID_CLIENT_TENANT", "")
    GRAPH_SENDER: str = os.getenv("GRAPH_SENDER", "")

    # Caminhos internos
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "cobranca.db"

    def graph_configured(self) -> bool:
        return all([
            self.GRAPH_CLIENT_ID,
            self.GRAPH_CLIENT_SECRET,
            self.GRAPH_TENANT,
            self.GRAPH_SENDER,
        ])


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
