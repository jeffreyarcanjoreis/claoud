"""Programmatic Alembic migration runner with pre-upgrade backup.

Applies pending migrations at startup following the project rules:

- the schema only ever changes through Alembic migrations;
- if the database file already exists AND there is a pending migration,
  a timestamped copy is made in backups_dir() BEFORE upgrading
  (no pending migration -> no backup);
- any migration error propagates and aborts startup (never swallowed).
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

from kairos.config import backups_dir, data_dir, database_url, db_path
from kairos.db import get_engine

logger = logging.getLogger(__name__)

# Project root derived from this file's location (never from the cwd), so the
# runner works no matter where the process was started from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    """Build an Alembic Config pointing at the project-root alembic.ini."""
    ini_path = _PROJECT_ROOT / "alembic.ini"
    if not ini_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {ini_path}")
    config = Config(str(ini_path))
    # Absolute script location, again independent of the cwd.
    config.set_main_option("script_location", str(_PROJECT_ROOT / "migrations"))
    return config


def _current_revision(engine: Engine) -> Optional[str]:
    """Return the revision currently stamped in the database (None if fresh)."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _backup_database(database_file: Path) -> Path:
    """Copy the database file into backups_dir() with a timestamped name."""
    target_dir = backups_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = target_dir / f"kairos-{timestamp}.db"
    shutil.copy2(database_file, backup_path)
    return backup_path


def run_migrations() -> None:
    """Bring the database schema up to the latest Alembic revision.

    Raises on any failure; errors are never swallowed. The file-based backup
    (rule 9) only applies to the local SQLite database; a remote database
    (e.g. Supabase/PostgreSQL, via KAIROS_DATABASE_URL) relies on the
    provider's own backups instead.
    """
    is_sqlite = database_url().startswith("sqlite")

    database_file: Optional[Path] = None
    database_existed = False
    if is_sqlite:
        data_dir().mkdir(parents=True, exist_ok=True)
        database_file = db_path()
        # Capture existence BEFORE opening any connection: connecting to a
        # missing SQLite file creates an empty one, which must not be backed up.
        database_existed = database_file.exists()

    config = _alembic_config()
    script_directory = ScriptDirectory.from_config(config)
    head_revision = script_directory.get_current_head()

    engine = get_engine()
    current_revision = _current_revision(engine)
    has_pending = current_revision != head_revision

    logger.info(
        "Database: %s | current revision: %s | head: %s | pending migrations: %s",
        database_file if is_sqlite else "<remote>",
        current_revision or "<none>",
        head_revision,
        "yes" if has_pending else "no",
    )

    if not has_pending:
        logger.info("Schema is up to date; no backup and no upgrade needed.")
        return

    if is_sqlite:
        assert database_file is not None
        if database_existed:
            backup_path = _backup_database(database_file)
            logger.info("Database backed up to %s before applying migrations.", backup_path)
        else:
            logger.info("Database file does not exist yet; creating it, no backup needed.")
    else:
        logger.info("Remote database; skipping file backup (relies on the provider's backups).")

    command.upgrade(config, "head")

    applied_revision = _current_revision(engine)
    logger.info(
        "Migrations applied: %s -> %s",
        current_revision or "<none>",
        applied_revision,
    )
