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

    # Identidade da instancia (permite varias carteiras, uma pasta por empresa)
    APP_CARTEIRA: str = os.getenv("APP_CARTEIRA", "Sinergas")
    # Porta do servidor local; mude para rodar duas instancias ao mesmo tempo
    APP_PORT: int = int(os.getenv("APP_PORT", "8756"))

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


# ---------------------------------------------------------------------------
# Caminho da planilha selecionado pelo usuario (persistido entre execucoes).
# Tem prioridade sobre o EXCEL_PATH do .env. Permite escolher o arquivo pela
# janela do app (file picker), sem editar o .env.
# ---------------------------------------------------------------------------
import json

CONFIG_FILE = settings.DATA_DIR / "app_config.json"


def _read_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def get_excel_path() -> str:
    """Caminho efetivo da planilha: escolha do usuario > .env."""
    escolhido = _read_config().get("excel_path")
    if escolhido and Path(escolhido).exists():
        return escolhido
    return settings.EXCEL_PATH


def set_excel_path(caminho: str) -> None:
    cfg = _read_config()
    cfg["excel_path"] = caminho
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def get_regua() -> dict:
    """Config da regua automatica: {ativa: bool, dias: [int]}."""
    cfg = _read_config()
    return {
        "ativa": bool(cfg.get("regua_ativa", False)),
        "dias": cfg.get("regua_dias", [7, 15, 30]),
    }


def set_regua(ativa: bool, dias: list) -> None:
    cfg = _read_config()
    cfg["regua_ativa"] = bool(ativa)
    # normaliza: inteiros unicos, ordenados, positivos
    dias_norm = sorted({int(d) for d in dias if int(d) > 0})
    cfg["regua_dias"] = dias_norm
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
