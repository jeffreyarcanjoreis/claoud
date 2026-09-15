# Scaffold do projeto, banco e migrações

## Descrição
Comportamento 10 do SPEC: quando o sistema é iniciado pela primeira vez, o banco de dados é criado automaticamente com as migrações. Cria o esqueleto do monólito FastAPI + SQLAlchemy + Alembic, com logs configurados e backup do arquivo do banco antes de cada migração (regras 5, 8 e 9 do architecture.md).

## Depende de
nenhuma

## Especificação funcional
- Ao iniciar a aplicação (`uvicorn kairos.main:app` ou via TestClient), se o arquivo do banco não existir, ele é criado automaticamente e todas as migrações Alembic são aplicadas até `head`.
- Se o banco já existe e há migrações pendentes, uma cópia de backup do arquivo (`kairos-YYYYMMDD-HHMMSS.db` em `data/backups/`) é feita ANTES de aplicar qualquer migração.
- Se o banco já existe e não há migração pendente, nada é copiado e o startup segue normal.
- A localização dos dados é configurável pela variável de ambiente `KAIROS_DATA_DIR` (default: `data/` na raiz do projeto). Testes usam diretório temporário.
- Logging configurado na aplicação inteira (formato com timestamp, nível via `KAIROS_LOG_LEVEL`, default INFO). O startup loga: caminho do banco, migrações aplicadas, backup feito (se houver).
- Endpoint `GET /health` responde `{"status": "ok"}` — prova mínima de que a app sobe.
- Caso de borda: falha ao aplicar migração não pode deixar o banco meio-migrado silenciosamente — o erro sobe e aborta o startup (regra 8: erro nunca engolido).

## Pré-condições
- Nenhuma (primeira issue). Python 3.14.5 disponível na máquina.
- Dependências novas: fastapi, uvicorn, sqlalchemy, alembic, pytest, httpx (testes). Instalação via `pip install -e .[dev]`.

## Arquivos a criar
- `pyproject.toml` — metadados do projeto `kairos`, dependências e extra `dev` (pytest, httpx)
- `.gitignore` — `__pycache__/`, `.venv/`, `data/`, `*.db`, `.pytest_cache/`, `*.egg-info/`
- `kairos/__init__.py` — pacote
- `kairos/config.py` — settings: `data_dir` (env `KAIROS_DATA_DIR`), `db_path`, `database_url`, `log_level`
- `kairos/log.py` — `setup_logging()` usado no startup
- `kairos/db.py` — engine SQLAlchemy, `SessionLocal`, `Base` (sem modelos ainda — modelos chegam na issue 02)
- `kairos/migrations_runner.py` — `run_migrations()`: detecta migração pendente, faz backup do arquivo se necessário, roda `alembic upgrade head` programaticamente
- `kairos/main.py` — `app` FastAPI com lifespan (setup_logging + run_migrations) e rota `GET /health`
- `alembic.ini` — configuração Alembic apontando para `migrations/`
- `migrations/env.py` — env do Alembic usando `kairos.config.database_url` e `Base.metadata`
- `migrations/script.py.mako` — template padrão
- `migrations/versions/0001_init.py` — revisão baseline vazia (prova que o pipeline funciona e cria a tabela `alembic_version`)
- `tests/test_scaffold.py` — com `KAIROS_DATA_DIR` temporário: (a) startup cria o banco e a tabela `alembic_version` em head; (b) `/health` retorna 200; (c) banco existente + migração pendente gera arquivo em `backups/` antes do upgrade; (d) sem pendência, não gera backup

## Arquivos a modificar
- Nenhum (greenfield — nada do que existe no repositório é tocado).

## Camadas envolvidas
configuração, banco/migração, aplicação (rota mínima), teste

## Status
concluída
