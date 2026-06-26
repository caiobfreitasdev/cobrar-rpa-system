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

# Procura o .env ao lado do executavel/projeto
load_dotenv(BASE_DIR / ".env")


class Settings:
    EXCEL_PATH: str = os.getenv("EXCEL_PATH", "")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")

    # Caminhos internos
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "cobranca.db"

    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_FROM)


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
