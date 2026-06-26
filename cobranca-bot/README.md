# Bot de Cobranca

Sistema **100% local** de cobranca de inadimplencia para empresa de contabilidade.
Le uma planilha Excel de contas a receber, sincroniza para um SQLite local, exibe um
dashboard reativo e envia e-mails de cobranca (HTML) — **um e-mail por boleto** —
somente apos **confirmacao manual de lote** pelo operador.

> Todo o dado e financeiro e sensivel: nada sai da maquina.

## Stack

- Backend: **Python + FastAPI**
- Frontend: HTML + CSS + JS (vanilla), servido pelo FastAPI em `localhost`
- Janela desktop: **pywebview**
- Banco: **SQLite** local
- Excel: **pandas + openpyxl** (le somente a aba `BASE`)
- Empacotamento: **PyInstaller** (`.exe` Windows)

## Estrutura

```
cobranca-bot/
├── app/
│   ├── main.py            # FastAPI + pywebview
│   ├── core/              # config (.env) e db (SQLite)
│   ├── services/          # excel_sync, titulos, email_sender
│   ├── rules/             # pendencias (flags TODO desligadas)
│   ├── api/routes.py      # endpoints
│   ├── templates/         # email_cobranca.html
│   └── web/               # dashboard (index.html, styles.css, app.js)
├── data/                  # cobranca.db (gerado em runtime)
├── .env.example
├── requirements.txt
└── build.spec
```

## Rodar em desenvolvimento

1. Crie e ative um ambiente virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Instale as dependencias:
   ```powershell
   pip install -r requirements.txt
   ```
3. Configure o `.env` (copie de `.env.example`):
   ```powershell
   Copy-Item .env.example .env
   ```
   Preencha `EXCEL_PATH` e as credenciais SMTP. **Nunca** comite o `.env`.
4. Inicie o app (a partir da pasta `cobranca-bot/`):
   ```powershell
   python -m app.main
   ```
   Abre a janela desktop (pywebview). Sem o pywebview, acesse
   `http://127.0.0.1:8756/` no navegador.

## Uso

1. **Recarregar planilha** — sincroniza a aba `BASE` com o banco. O resumo
   (novos / alterados / baixados) aparece no painel lateral.
2. Filtre e ordene os titulos; selecione com os checkboxes.
3. **Enviar lote** — abre um resumo/preview. O envio so ocorre apos
   **confirmacao explicita**. Titulos sem e-mail ficam pendentes (nao enviados).
4. A coluna **Status** mostra "Nao cobrado" ou "Cobrado em DD/MM/AAAA".

## Sincronizacao (a cada carga)

- Chave de negocio: `cd_cliente + titulo`.
- Calcula `hash_linha` dos campos relevantes para detectar alteracoes.
- Novo → insere; hash diferente → atualiza; mesmo hash → mantem.
- Titulos que sumiram da carga → `ativo = 0` (provavel pagamento). Nao deleta.

## Colunas novas (em construcao)

- `Email` (ao lado de `Cliente`) e `Link de Cobranca` sao lidas **se existirem**;
  caso contrario, os campos ficam vazios sem quebrar o sync.

## Pendencias antes de producao (flags desligadas)

Em `app/rules/pendencias.py` (todas `False` nesta fase):

- `TRAVA_STATUS` — bloquear envio para JURIDICO / NEGATIVADO / ACORDO
  (coluna STATUS ainda nao existe na BASE; gancho pronto).
- `REGUA_AUTOMATICA` — regua de cobranca automatica por dias de atraso
  (hoje o envio e sempre manual com confirmacao de lote).

O dashboard exibe essas pendencias no painel lateral.

## Gerar o `.exe` (Windows)

```powershell
pip install -r requirements.txt
pyinstaller build.spec
```

O executavel sai em `dist/BotCobranca.exe`. Coloque o `.env` **ao lado do `.exe`**
(o app procura o `.env` e cria a pasta `data/` no mesmo diretorio do executavel).

## Seguranca

- Credenciais SMTP somente via `.env` (nunca hardcode).
- `.gitignore` cobre `.env`, `data/*.db` e arquivos Excel fiscais (`*.xlsx`).
- Aplicacao roda apenas em `127.0.0.1`.
```
