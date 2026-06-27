"""Conexao e criacao de schema SQLite."""
import sqlite3
from contextlib import contextmanager

from app.core.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS titulos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uf TEXT,
    cd_cliente TEXT NOT NULL,
    cliente TEXT,
    email TEXT,
    titulo TEXT NOT NULL,
    doc_fiscal TEXT,
    vl_titulo REAL,
    juros REAL,
    multa REAL,
    total_atualizado REAL,
    emissao DATE,
    vencimento DATE,
    dias_atraso INTEGER,
    obs TEXT,
    link_cobranca TEXT,
    hash_linha TEXT,
    ativo INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (cd_cliente, titulo)
);

CREATE TABLE IF NOT EXISTS envios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo_id INTEGER NOT NULL,
    data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status_envio TEXT,
    canal TEXT DEFAULT 'email',
    origem TEXT DEFAULT 'manual',   -- manual | lote | agendado | regua
    regra_dias INTEGER,             -- regra da regua que disparou (se houver)
    erro TEXT,
    FOREIGN KEY (titulo_id) REFERENCES titulos (id)
);

CREATE TABLE IF NOT EXISTS agendamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo_id INTEGER NOT NULL,
    data_agendada TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'pendente',  -- pendente | executado | cancelado | erro
    erro TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executado_em TIMESTAMP,
    FOREIGN KEY (titulo_id) REFERENCES titulos (id)
);

CREATE INDEX IF NOT EXISTS idx_titulos_ativo ON titulos (ativo);
CREATE INDEX IF NOT EXISTS idx_envios_titulo ON envios (titulo_id);
CREATE INDEX IF NOT EXISTS idx_agend_status ON agendamentos (status);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrar(conn) -> None:
    """Adiciona colunas novas em bancos criados em versoes anteriores."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(envios)")}
    if "origem" not in cols:
        conn.execute("ALTER TABLE envios ADD COLUMN origem TEXT DEFAULT 'manual'")
    if "regra_dias" not in cols:
        conn.execute("ALTER TABLE envios ADD COLUMN regra_dias INTEGER")


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(SCHEMA)
        _migrar(conn)
