# Bot de Cobranca

Sistema **100% local** de cobranca de inadimplencia para empresa de contabilidade.
Le uma planilha Excel de contas a receber, sincroniza para um SQLite local, exibe um
dashboard em abas e envia e-mails de cobranca (HTML) via **Microsoft Graph** —
**um e-mail por boleto** — individual, em lote, agendado ou por regua automatica.

> Todo o dado e financeiro e sensivel: nada sai da maquina alem dos e-mails.

## Stack

- Backend: **Python + FastAPI** + scheduler em thread (agendamentos/regua)
- Frontend: HTML + CSS + JS (vanilla), servido pelo FastAPI em `localhost`
- Janela desktop: **pywebview** (com file picker nativo para a planilha)
- Banco: **SQLite** local
- Excel: **pandas + openpyxl** (le somente a aba `BASE`)
- E-mail: **Microsoft Graph API** (client credentials)
- Empacotamento: **PyInstaller** (`.exe` Windows)

## Estrutura

```
cobranca-bot/
├── app/
│   ├── main.py            # FastAPI + pywebview + scheduler (60s)
│   ├── core/              # config (.env, excel_path, regua) e db (SQLite)
│   ├── services/          # excel_sync, titulos, email_sender, graph_client,
│   │                      # relatorios, agendamentos
│   ├── rules/             # pendencias (trava de STATUS desligada)
│   ├── api/routes.py      # endpoints
│   ├── templates/         # email_cobranca.html
│   └── web/               # dashboard em abas (index.html, styles.css, app.js)
├── data/                  # cobranca.db + app_config.json (runtime)
├── scripts/               # gerar_base_teste.py
├── .env.example
├── requirements.txt
└── build.spec
```

## Rodar em desenvolvimento

1. Ambiente e dependencias:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Configure o `.env` (copie de `.env.example`) com as credenciais do
   **Microsoft Graph**: `ID_CLIENT_ID`, `ID_CLIENT_SECRET`, `ID_CLIENT_TENANT`,
   `GRAPH_SENDER`. **Nunca** comite o `.env`.

   > Pre-requisito no Azure: App Registration com permissao de APLICACAO
   > `Mail.Send` e consentimento de admin. O client secret expira — renove
   > e atualize o `.env` quando necessario.
3. Inicie (a partir da pasta `cobranca-bot/`):
   ```powershell
   python -m app.main
   ```
   Sem o pywebview, acesse `http://127.0.0.1:8756/` no navegador.

## Uso

**Aba Cobrancas**
1. **Selecionar planilha** — escolhe o `.xlsx` no explorador (fica salvo).
2. **Recarregar planilha** — sincroniza a aba `BASE` (novos/alterados/baixados).
3. Envio **individual** (botao Enviar na linha) ou **em lote** (checkboxes),
   sempre com confirmacao. Titulos sem e-mail ficam pendentes.
4. **Agendar selecionados** — data/hora futura para envio automatico.

**Aba Relatorio** — historico de envios com status, origem (Individual/Lote/
Agendado/Regua) e erros; botao **Exportar CSV** (abre no Excel pt-BR).

**Aba Agendamento** — regua automatica (marcos de dias de atraso, um envio
por marco) e lista de agendamentos manuais com cancelamento.

> O scheduler roda a cada 60s **enquanto o app esta aberto**. Agendamento de
> titulo que foi baixado na planilha (provavel pagamento) e cancelado
> automaticamente — o sistema nunca cobra quem ja pagou.

## Sincronizacao (a cada carga)

- Chave de negocio: `cd_cliente + titulo`.
- `hash_linha` detecta alteracoes relevantes (valores, vencimento, email, link).
- **Dias de atraso sao calculados internamente** (hoje - vencimento), sempre
  atuais mesmo sem recarregar a planilha.
- Novo → insere; hash diferente → atualiza; mesmo hash → mantem.
- Titulos que sumiram da carga → `ativo = 0` (provavel pagamento). Nao deleta.
- Colunas `Email` e `Link de Cobranca` sao lidas **se existirem**.

## Gerar o `.exe` (Windows)

```powershell
pip install -r requirements.txt
pyinstaller build.spec
```

O executavel sai em `dist/BotCobranca.exe`. Coloque o `.env` **ao lado do
`.exe`** (o app procura o `.env` e cria a pasta `data/` no mesmo diretorio).

## Seguranca

- Credenciais do Graph somente via `.env` (contem o client secret — trate
  como senha; so em maquinas autorizadas).
- `.gitignore` cobre `.env`, `data/*.db` e arquivos Excel fiscais (`*.xlsx`).
- Aplicacao roda apenas em `127.0.0.1`.
