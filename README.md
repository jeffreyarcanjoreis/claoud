# Kairos — plataforma de gestão do coach

Aplicação web (FastAPI + SQLAlchemy, templates server-rendered) que suporta o
Método Kairos: cadastro e ficha de alunos, avaliações, treinos, agenda,
acompanhamento, financeiro e o funil de captação (cadastro público → lead →
aluno).

## Requisitos

- **Python 3.14+**
- SQLite ≥ 3.35 (já vem com o Python) para rodar local, ou um Postgres
  (ex.: Supabase) para rodar na nuvem.

## Instalação

```bash
# na raiz do projeto (recomendado usar um ambiente virtual)
pip install -e ".[dev]"
```

Isso instala o app e as dependências de teste (pytest, httpx).

## Configuração (arquivo `.env`)

O app lê um arquivo **`.env`** na raiz (é **git-ignored** — guarde segredos aí,
eles nunca vão para o repositório). Todas as variáveis são opcionais; sem elas,
o app roda 100% local no SQLite.

| Variável | Para quê |
|---|---|
| `KAIROS_DATABASE_URL` | Connection string do Postgres/Supabase. **Se ausente, usa o SQLite local** (`data/kairos.db`). Uma URL `postgresql://…` é normalizada automaticamente para o driver `pg8000` (puro-Python). |
| `KAIROS_GCAL_ICS_URL` | Link **secreto** iCal (`.ics`) do Google Calendar, para a aba Agenda → Google Calendar (só-leitura). |
| `KAIROS_DATA_DIR` | Diretório dos dados locais (padrão: `./data`). |
| `KAIROS_LOG_LEVEL` | Nível de log (padrão: `INFO`). |

Exemplo de `.env`:

```dotenv
# Sem esta linha, o app usa o SQLite local (data/kairos.db).
KAIROS_DATABASE_URL=postgresql://USUARIO:SENHA@HOST:5432/postgres

# Link secreto iCal do Google Calendar (Configurações do calendário →
# "Integrar agenda" → "Endereço secreto no formato iCal").
KAIROS_GCAL_ICS_URL=https://calendar.google.com/calendar/ical/.../private-.../basic.ics
```

> **Segurança:** o `.env` contém credenciais (senha do banco, link secreto do
> calendário). Ele está no `.gitignore` e as URLs com senha são **mascaradas nos
> logs** (`…:***@…`). Não cole esses valores em lugares públicos.

## Como rodar

```bash
python -m uvicorn kairos.main:app --port 8000
```

Abra `http://localhost:8000`. As **migrações do banco rodam automaticamente no
arranque** (Alembic): o schema é levado até a última revisão antes do app
atender requisições. No SQLite, um backup do arquivo é feito antes de migrar; num
banco remoto, confia-se no backup do provedor (ex.: Supabase).

A vitrine pública fica em `http://localhost:8000/vitrine` e o cadastro de
Avaliação Inicial em `http://localhost:8000/comecar`.

## Banco de dados: local vs nuvem

- **Local (padrão):** sem `KAIROS_DATABASE_URL`, tudo vive em `data/kairos.db`
  (SQLite). Ótimo para desenvolvimento.
- **Nuvem (Supabase/Postgres):** com `KAIROS_DATABASE_URL` setada, o app usa o
  Postgres. **Quando ela está setada, o Supabase é a fonte de verdade** — o
  `data/kairos.db` local deixa de ser usado (vira uma cópia parada). Editar um
  não reflete no outro. Para voltar ao local, remova/comente a variável no `.env`.

> **Atenção — Postgres impõe foreign keys; o SQLite não** (por padrão). Um
> comportamento que "funciona" no SQLite pode falhar no Postgres se apagar um
> registro antes dos que dependem dele. Ao mexer em exclusões, respeite a ordem
> filho → pai.

## Testes

```bash
python -m pytest -q
```

Os testes **sempre rodam num SQLite isolado e temporário** e **nunca tocam o
banco remoto**: mesmo com `KAIROS_DATABASE_URL` no `.env`, um fixture em
`tests/conftest.py` remove essa variável durante os testes.

## Cenário de demonstração

Para popular um aluno-demo completo (lead → aluno → plano/pagamento → avaliação
→ treino → sessões → tarefas → acompanhamento) e navegar pelo app com dados:

```bash
python -m kairos.cli semear-demo            # cria a demo "Ana Demonstração"
python -m kairos.cli semear-demo --remover  # remove só a demo
```

O comando age no banco configurado (Supabase se `KAIROS_DATABASE_URL` estiver
setada; senão, o SQLite local) e **nunca toca dados reais** — filtra pelo nome da
demo.

## Importar aluno de planilha

```bash
python -m kairos.cli importar-aluno "<pasta do aluno>" [--simular]
```

## Estrutura

- `kairos/` — o app, organizado por comportamento (`alunos/`, `avaliacoes/`,
  `treinos/`, `agenda/`, `acompanhamento/`, `financeiro/`, `contatos/`,
  `tarefas/`, `vitrine/`, `painel/`), cada um com `models` / `service` / `routes`.
- `migrations/` — migrações Alembic (schema só muda por aqui).
- `tests/` — a suíte pytest.
- `issues/` — as fatias planejadas; `issues/done/` as concluídas.
- `CHANGELOG.md` — histórico das fatias entregues.
