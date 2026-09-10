"""Tests for issue 01: project scaffold, database and migrations.

Covers the functional specification:
- app startup (lifespan) creates the database file and stamps alembic_version
  at the head revision ("0020");
- GET /health returns 200 with {"status": "ok"};
- existing database + pending migration -> a backup file is created in
  backups/ BEFORE the upgrade;
- no pending migration -> no backup;
- first run (no database file yet) -> no backup.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

import kairos.db
from kairos.main import app
from kairos.migrations_runner import run_migrations

HEAD_REVISION = "0024"  # bumped by migration 0024_create_reconhecimentos_nivel


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def _stamped_revision(db_file: Path) -> Optional[str]:
    """Read the revision recorded in alembic_version of a SQLite file."""
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        with engine.connect() as connection:
            row = connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).fetchone()
        return row[0] if row else None
    finally:
        engine.dispose()


def _backup_files(data_dir: Path) -> list[Path]:
    backups = data_dir / "backups"
    if not backups.exists():
        return []
    return sorted(backups.glob("kairos-*.db"))


def test_app_startup_creates_database_at_head_revision(data_dir: Path) -> None:
    db_file = data_dir / "kairos.db"
    assert not db_file.exists()

    with TestClient(app):  # entering the context runs the lifespan
        assert db_file.exists()

    assert _stamped_revision(db_file) == HEAD_REVISION


def test_health_endpoint_returns_ok(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_pending_migration_on_existing_database_creates_backup_before_upgrade(
    data_dir: Path,
) -> None:
    # First run: database is created and stamped at head. No backup expected.
    run_migrations()
    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert _backup_files(data_dir) == []

    # Simulate a pending migration: run the real Alembic downgrade back to
    # the previous revision (0017 is an ALTER on the "alunos" table, so
    # reversing it through Alembic itself -- rather than a raw DROP TABLE --
    # is what actually leaves the schema consistent with revision 0016) so
    # the existing database looks older than head and the upgrade can
    # re-run.
    from alembic import command as alembic_command

    from kairos.migrations_runner import _alembic_config

    alembic_command.downgrade(_alembic_config(), "0016")

    # Second run: existing file + pending migration -> exactly one backup.
    run_migrations()

    backups = _backup_files(data_dir)
    assert len(backups) == 1, f"expected exactly 1 backup, found: {backups}"

    # The backup is the pre-upgrade snapshot (still at the previous
    # revision), proving it was taken BEFORE the migration ran; the live
    # database is at head.
    assert _stamped_revision(backups[0]) == "0016"
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_no_pending_migration_does_not_create_backup(data_dir: Path) -> None:
    run_migrations()
    assert _backup_files(data_dir) == []

    # Database exists and is already at head: nothing to do, no backup.
    run_migrations()

    assert _backup_files(data_dir) == []
    assert _stamped_revision(data_dir / "kairos.db") == HEAD_REVISION


def test_first_run_with_no_database_does_not_create_backup(data_dir: Path) -> None:
    assert not (data_dir / "kairos.db").exists()

    run_migrations()

    assert (data_dir / "kairos.db").exists()
    assert _backup_files(data_dir) == []
