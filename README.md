# Cobrar - Sistema de Cobranca (RPA)

Sistema **100% local** de cobranca de inadimplencia para empresa de contabilidade.
Le uma planilha Excel de contas a receber, sincroniza para um SQLite local e envia
e-mails de cobranca (HTML) via **Microsoft Graph** — **um e-mail por boleto** —
individual, em lote, agendado ou por regua automatica de dias de atraso.

> Todo o dado e financeiro e sensivel: **nada sai da maquina** alem dos e-mails.

## Onde esta o codigo

O projeto fica na pasta [`cobranca-bot/`](cobranca-bot/). Veja o
[README detalhado](cobranca-bot/README.md) para instrucoes completas de instalacao,
execucao e empacotamento. Convencoes e processos em [CLAUDE.md](CLAUDE.md).

## Stack

- Backend: **Python + FastAPI** (+ scheduler em background p/ agendamentos)
- Frontend: HTML + CSS + JS (vanilla), dashboard em abas, servido em `localhost`
- Janela desktop: **pywebview**
- Banco: **SQLite** local
- Excel: **pandas + openpyxl** (le somente a aba `BASE`)
- E-mail: **Microsoft Graph API** (client credentials + `Mail.Send`)
- Empacotamento: **PyInstaller** (`.exe` Windows)

## Inicio rapido

```powershell
cd cobranca-bot
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # preencha as credenciais do Microsoft Graph
python -m app.main
```

A planilha pode ser escolhida pelo botao **Selecionar planilha** dentro do app.

## Funcionalidades

- **Cobrancas**: envio individual por linha ou em lote, com confirmacao.
- **Relatorio**: historico de envios (status, origem, erro) + exportacao CSV.
- **Agendamento**: data/hora manual por titulo + regua automatica por marcos
  de dias de atraso (o app precisa estar aberto para o disparo).

## Seguranca

- Credenciais somente via `.env` (ignorado no git; contem o client secret do Azure).
- `.gitignore` cobre `.env`, bancos `*.db` e planilhas fiscais (`*.xlsx`).
- Aplicacao roda apenas em `127.0.0.1`. Repositorio deve ser **privado**.
