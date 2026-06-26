# CLAUDE.md — Guia do projeto Cobrar (Bot de Cobranca)

Este arquivo orienta o Claude Code (e qualquer dev) sobre o projeto: contexto,
convencoes, processos e pendencias. Leia antes de mexer no codigo.

## Contexto e principios inegociaveis

- Sistema de **cobranca de inadimplencia** para empresa de contabilidade.
- **100% local**: dados financeiros sensiveis **nunca** saem da maquina.
- **Credenciais somente via `.env`** — nunca hardcode SMTP/senhas no codigo.
- **Envio sempre manual com confirmacao de lote**. Nenhum disparo automatico.
- **Um e-mail por boleto**.
- Ler **somente a aba `BASE`** do Excel. Demais abas sao ignoradas nesta fase.

## Estrutura

```
cobranca-bot/
├── app/
│   ├── main.py            # FastAPI + pywebview (porta 8756)
│   ├── core/              # config (.env) e db (SQLite + schema)
│   ├── services/          # excel_sync, titulos, email_sender
│   ├── rules/pendencias.py# flags de producao (TODO, desligadas)
│   ├── api/routes.py      # endpoints REST
│   ├── templates/         # email_cobranca.html
│   └── web/               # dashboard (index.html, styles.css, app.js)
├── data/                  # cobranca.db (runtime, ignorado no git)
├── .env.example           # modelo; o .env real NAO vai pro git
├── requirements.txt
└── build.spec             # PyInstaller
```

## Como rodar

```powershell
cd cobranca-bot
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # preencher EXCEL_PATH + SMTP
python -m app.main
```

Sem pywebview, acesse `http://127.0.0.1:8756/`.

## Regras de sincronizacao (excel_sync.py)

- Chave de negocio unica: `cd_cliente + titulo`.
- `hash_linha` calculado de: vl_titulo, juros, multa, total_atualizado,
  vencimento, dias_atraso, email, link_cobranca.
- Novo -> insere; hash diferente -> atualiza; mesmo hash -> mantem.
- Sumiu da carga -> `ativo = 0` (provavel pagamento). **Nunca deletar.**
- Colunas `Email` e `Link de Cobranca` sao lidas **se existirem**; senao ficam vazias.

## Pendencias antes de producao (flags desligadas + TODO)

Em `app/rules/pendencias.py`:

- `TRAVA_STATUS = False` — bloquear envio para JURIDICO / NEGATIVADO / ACORDO.
  Coluna STATUS ainda nao existe na BASE; gancho `bloquear_envio()` ja pronto.
- `REGUA_AUTOMATICA = False` — regua de cobranca por dias de atraso.
  Hoje o envio e sempre manual.

**Nao implementar agora:** trava de STATUS, regua automatica, integracao real do
link de cartao, leitura de outras abas, qualquer envio sem confirmacao.

## Processo de Git / commits

- **Commits NAO sao automaticos.** Cada commit/push e feito manualmente, quando
  voce pede. O Claude nunca commita sozinho.
- Repositorio: https://github.com/caiobfreitasdev/cobrar-rpa-system (manter **privado**).
- Branch principal: `main`.
- Fluxo padrao (a partir da raiz do projeto):
  ```powershell
  git add -A
  git commit -m "descricao clara da mudanca"
  git push
  ```
- **Antes de commitar**, conferir `git status --short` e garantir que `.env`,
  `*.db` e `*.xlsx` NAO aparecem na lista.
- Mensagens de commit em portugues, no imperativo, descrevendo o "porque".

## Convencoes de codigo

- Python: nomes e comentarios em portugues (sem acentos no codigo para evitar
  problemas de encoding), seguindo o estilo existente.
- Sem dependencias novas sem necessidade clara.
- Frontend vanilla (sem framework). Mesmo padrao visual no dashboard e no e-mail.

## Verificacao rapida antes de entregar

```powershell
cd cobranca-bot
python -m py_compile app/main.py app/core/*.py app/services/*.py app/rules/*.py app/api/*.py
```
