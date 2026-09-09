"""Alembic environment for the Kairos project.

The database URL is never read from alembic.ini: it is always resolved at
runtime through kairos.config.database_url(), so the same configuration works
in any environment (KAIROS_DATA_DIR). Logging is handled by the application
(kairos.log); this env.py does not call logging.fileConfig.
"""

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

# Make the `kairos` package importable when Alembic is invoked from the CLI
# with an arbitrary working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from kairos.config import database_url  # noqa: E402
from kairos.db import Base  # noqa: E402

# Import all model modules so their tables register on Base.metadata
# (required for autogenerate support).
import kairos.agenda.models  # noqa: E402,F401
import kairos.alunos.models  # noqa: E402,F401
import kairos.auth.models  # noqa: E402,F401
import kairos.avaliacoes.models  # noqa: E402,F401

config = context.config

# Metadata of all Kairos models, used for autogenerate support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode: emit SQL without a DBAPI connection."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode: connect and apply directly.

    If the caller supplied a live connection via config.attributes
    (e.g. kairos.migrations_runner), reuse it; otherwise build an engine
    from the runtime-resolved database URL.
    """
    connection = config.attributes.get("connection", None)

    if connection is not None:
        _run_with_connection(connection)
        return

    engine = create_engine(database_url())
    try:
        with engine.connect() as conn:
            _run_with_connection(conn)
    finally:
        engine.dispose()


def _run_with_connection(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
