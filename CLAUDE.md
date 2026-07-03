# CLAUDE.md — Guia do projeto Cobrar (Bot de Cobranca)

Este arquivo orienta o Claude Code (e qualquer dev) sobre o projeto: contexto,
convencoes, processos e pendencias. Leia antes de mexer no codigo.

## Contexto e principios inegociaveis

- Sistema de **cobranca de inadimplencia** para empresa de contabilidade.
- **100% local**: dados financeiros sensiveis **nunca** saem da maquina
  (exceto os proprios e-mails de cobranca, via Microsoft Graph).
- **Credenciais somente via `.env`** — nunca hardcode segredos no codigo.
- Envio **individual e em lote** sempre com confirmacao do operador.
  Disparos automaticos existem apenas quando o operador configura
  explicitamente (agendamento manual ou regua automatica).
- **Um e-mail por boleto**.
- Ler **somente a aba `BASE`** do Excel. Demais abas sao ignoradas.

## Estrutura

```
cobranca-bot/
├── app/
│   ├── main.py            # FastAPI + pywebview (porta 8756) + scheduler (60s)
│   ├── core/
│   │   ├── config.py      # .env, resource_path (exe), excel_path e regua persistidos
│   │   └── db.py          # SQLite: titulos, envios, agendamentos + agora_local()
│   ├── services/
│   │   ├── excel_sync.py  # le aba BASE, hash, upsert, baixa logica
│   │   ├── titulos.py     # consultas do dashboard + DIAS_ATRASO_SQL (calculado)
│   │   ├── email_sender.py# render do template + envio + log em envios
│   │   ├── graph_client.py# token OAuth2 (client credentials) + sendMail
│   │   ├── relatorios.py  # relatorio de envios + export CSV
│   │   └── agendamentos.py# agendamento manual + regua automatica (scheduler)
│   ├── rules/pendencias.py# trava de STATUS (flag desligada) + painel de pendencias
│   ├── api/routes.py      # endpoints REST
│   ├── templates/         # email_cobranca.html (tabela, CSS inline)
│   └── web/               # dashboard em abas (Cobrancas/Relatorio/Agendamento)
├── data/                  # cobranca.db + app_config.json (runtime, fora do git)
├── scripts/gerar_base_teste.py
├── .env.example
├── requirements.txt
└── build.spec             # PyInstaller (collect_all: numpy/pandas/certifi)
```

## Como rodar

```powershell
cd cobranca-bot
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # preencher credenciais do Graph
python -m app.main
```

Sem pywebview, acesse `http://127.0.0.1:8756/`.

`.env` (ver `.env.example`): `EXCEL_PATH` (opcional — da para escolher pelo
botao "Selecionar planilha"), `ID_CLIENT_ID`, `ID_CLIENT_SECRET`,
`ID_CLIENT_TENANT`, `GRAPH_SENDER`.

## Envio de e-mail (Microsoft Graph)

- Fluxo **client credentials** (app-only): token em
  `login.microsoftonline.com/{tenant}` + `POST /users/{sender}/sendMail`.
- Pre-requisito no Azure: permissao de APLICACAO `Mail.Send` com admin consent.
- O client secret **expira** — renovar no Azure e atualizar o `.env`.
- Todo envio e logado em `envios` com `origem`: manual | lote | agendado | regua.

## Regras de sincronizacao (excel_sync.py)

- Chave de negocio unica: `cd_cliente + titulo`.
- `hash_linha` calculado de: vl_titulo, juros, multa, total_atualizado,
  vencimento, email, link_cobranca. **dias_atraso NAO entra no hash**.
- `dias_atraso` e **calculado internamente** (hoje - vencimento, nunca
  negativo) via `DIAS_ATRASO_SQL`; o valor da planilha e so fallback.
- Novo -> insere; hash diferente -> atualiza; mesmo hash -> mantem.
- Sumiu da carga -> `ativo = 0` (provavel pagamento). **Nunca deletar.**
- Colunas `Email` e `Link de Cobranca` sao lidas **se existirem**.
- Timestamps sempre em **hora local** via `agora_local()` (o
  CURRENT_TIMESTAMP do SQLite e UTC — nao usar em INSERT/UPDATE).

## Agendamento e regua (agendamentos.py)

- Scheduler roda em thread a cada 60s **enquanto o app esta aberto**.
- Agendamento manual: data/hora **futura** obrigatoria; titulo que virou
  `ativo = 0` antes do disparo e **cancelado** com motivo (nunca cobrar
  quem ja pagou).
- Regua automatica: marcos de dias de atraso (config em
  `data/app_config.json`), um envio por marco (dedup por `regra_dias`).
- Regua e agendamento so agem quando o operador ativa/agenda.

## Pendencias antes de producao

- `TRAVA_STATUS = False` em `app/rules/pendencias.py` — bloquear envio para
  JURIDICO / NEGATIVADO / ACORDO. Coluna STATUS ainda nao existe na BASE;
  gancho `bloquear_envio()` pronto.
- Integracao real do link de cartao (coluna em construcao na planilha).
- Renovacao do client secret do Azure (expira).

**Nao implementar sem pedido explicito:** trava de STATUS, leitura de outras
abas, qualquer envio sem acao do operador.

## Processo de Git / commits

- **Commits NAO sao automaticos.** Cada commit/push e feito manualmente,
  quando voce pede. O Claude nunca commita sozinho.
- Repositorio: https://github.com/caiobfreitasdev/cobrar-rpa-system (manter **privado**).
- Branch principal: `main`.
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

## Build do .exe

```powershell
pyinstaller build.spec   # gera dist/BotCobranca.exe
```

O exe le o `.env` **ao lado dele** e cria `data/` no mesmo diretorio.
Recursos (templates/web) resolvidos via `resource_path()` (sys._MEIPASS).
