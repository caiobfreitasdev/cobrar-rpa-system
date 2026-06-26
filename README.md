# Cobrar - Sistema de Cobranca (RPA)

Sistema **100% local** de cobranca de inadimplencia para empresa de contabilidade.
Le uma planilha Excel de contas a receber, sincroniza para um SQLite local, exibe um
dashboard reativo e envia e-mails de cobranca (HTML) — **um e-mail por boleto** —
somente apos **confirmacao manual de lote** pelo operador.

> Todo o dado e financeiro e sensivel: **nada sai da maquina**.

## Onde esta o codigo

O projeto fica na pasta [`cobranca-bot/`](cobranca-bot/). Veja o
[README detalhado](cobranca-bot/README.md) para instrucoes completas de instalacao,
execucao e empacotamento.

## Stack

- Backend: **Python + FastAPI**
- Frontend: HTML + CSS + JS (vanilla), servido em `localhost`
- Janela desktop: **pywebview**
- Banco: **SQLite** local
- Excel: **pandas + openpyxl** (le somente a aba `BASE`)
- Empacotamento: **PyInstaller** (`.exe` Windows)

## Inicio rapido

```powershell
cd cobranca-bot
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # preencha EXCEL_PATH e credenciais SMTP
python -m app.main
```

## Estado atual

Scaffold inicial entregue: sync Excel -> SQLite, dashboard e envio com confirmacao
de lote. Regras de producao (trava de STATUS, regua automatica) estao como **flags
desligadas + TODO**. Detalhes e pendencias em [CLAUDE.md](CLAUDE.md).

## Seguranca

- Credenciais somente via `.env` (ignorado no git).
- `.gitignore` cobre `.env`, bancos `*.db` e planilhas fiscais (`*.xlsx`).
- Aplicacao roda apenas em `127.0.0.1`. Repositorio deve ser **privado**.
