"""Copia todos os dados do kairos.db (SQLite) para o Supabase (PostgreSQL).

Uso (a partir da raiz do projeto, com o venv ativo)::

    python scripts/migrar_sqlite_para_supabase.py "postgresql://postgres:SENHA@db.xxxx.supabase.co:5432/postgres"

Ou, se KAIROS_DATABASE_URL já estiver definida no ambiente/.env apontando
para o Supabase::

    python scripts/migrar_sqlite_para_supabase.py

Passos:

1. Aplica as migrações Alembic no banco de destino (cria o schema, se ainda
   não existir).
2. Copia as linhas de cada tabela do SQLite local para o Postgres, na ordem
   de dependência de chaves estrangeiras (rule 5: schema só muda via
   Alembic; este script só copia dados, nunca dados sintéticos — rule 6).
3. Ajusta as sequências do Postgres (SERIAL/IDENTITY) para o próximo valor
   livre, já que os IDs são inseridos explicitamente.

Erros nunca são engolidos (rule 8): qualquer falha aborta o processo com o
traceback completo. Não apaga nem sobrescreve o kairos.db local.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, insert, select  # noqa: E402

from kairos.config import database_url, db_path  # noqa: E402
from kairos.db import Base  # noqa: E402
from kairos.log import setup_logging  # noqa: E402

# Importa todos os módulos de domínio para que suas tabelas sejam
# registradas em Base.metadata antes de iterá-la.
import kairos.acompanhamento.models  # noqa: E402,F401
import kairos.agenda.models  # noqa: E402,F401
import kairos.alunos.models  # noqa: E402,F401
import kairos.avaliacoes.models  # noqa: E402,F401
import kairos.contatos.models  # noqa: E402,F401
import kairos.financeiro.models  # noqa: E402,F401
import kairos.tarefas.models  # noqa: E402,F401
import kairos.treinos.models  # noqa: E402,F401

import logging  # noqa: E402

logger = logging.getLogger(__name__)


def _normalize_target_url(raw: str) -> str:
    for prefix in ("postgres://", "postgresql://"):
        if raw.startswith(prefix) and not raw.startswith("postgresql+"):
            return "postgresql+pg8000://" + raw[len(prefix):]
    return raw


def _apply_migrations(target_url: str) -> None:
    """Run Alembic "upgrade head" against the target database."""
    ini_path = _PROJECT_ROOT / "alembic.ini"
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "migrations"))

    engine = create_engine(target_url)
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()


def _reset_sequence(connection, table_name: str, pk_column: str) -> None:
    """Advance the PostgreSQL sequence of an identity PK past its max value."""
    preparer = connection.dialect.identifier_preparer
    quoted_table = preparer.quote(table_name)
    quoted_column = preparer.quote(pk_column)
    connection.exec_driver_sql(
        "SELECT setval(pg_get_serial_sequence(%s, %s), "
        f"COALESCE((SELECT MAX({quoted_column}) FROM {quoted_table}), 1), "
        f"(SELECT MAX({quoted_column}) FROM {quoted_table}) IS NOT NULL)",
        (table_name, pk_column),
    )


def _copy_data(source_url: str, target_url: str) -> None:
    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)
    try:
        with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
            for table in Base.metadata.sorted_tables:
                rows = [dict(row._mapping) for row in source_conn.execute(select(table))]
                if not rows:
                    logger.info("%s: 0 linhas (nada a copiar).", table.name)
                    continue

                target_conn.execute(insert(table), rows)
                logger.info("%s: %d linha(s) copiada(s).", table.name, len(rows))

                pk_columns = [col.name for col in table.primary_key.columns]
                if len(pk_columns) == 1 and table.columns[pk_columns[0]].autoincrement:
                    _reset_sequence(target_conn, table.name, pk_columns[0])
    finally:
        source_engine.dispose()
        target_engine.dispose()


def main() -> int:
    setup_logging()

    target_raw = sys.argv[1] if len(sys.argv) > 1 else None
    if target_raw is None:
        env_url = database_url()
        if env_url.startswith("sqlite"):
            print(
                "Uso: python scripts/migrar_sqlite_para_supabase.py "
                "<connection-string-do-supabase>\n"
                "(ou defina KAIROS_DATABASE_URL apontando para o Supabase antes de rodar)"
            )
            return 1
        target_url = env_url
    else:
        target_url = _normalize_target_url(target_raw)

    source_path = db_path()
    if not source_path.exists():
        print(f"Banco SQLite local não encontrado em {source_path}.")
        return 1
    source_url = f"sqlite:///{source_path.resolve().as_posix()}"

    logger.info("Origem: %s", source_url)
    logger.info("Destino: %s", target_url.split("@")[-1])

    logger.info("Aplicando migrações Alembic no destino...")
    _apply_migrations(target_url)

    logger.info("Copiando dados...")
    _copy_data(source_url, target_url)

    logger.info("Migração concluída.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
