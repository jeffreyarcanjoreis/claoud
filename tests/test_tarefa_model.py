"""Tests for the Tarefa model and migration (0011_create_tarefas).

Covers the functional specification:
- after migrating, the "tarefas" table exists and the database is stamped at
  the head revision ("0015");
- the table has exactly the expected columns -- no derived columns are
  stored;
- inserting a Tarefa with only the required "titulo" field works end to end:
  categoria and prazo round-trip as None (never a fabricated default),
  concluida round-trips as False (the server default), and created_at is
  populated by the server.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa

import kairos.db
from kairos.db import session_scope
from kairos.migrations_runner import run_migrations
from kairos.tarefas.models import Tarefa

HEAD_REVISION = "0022"  # bumped by migration 0022_create_registros_treino


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


def _table_names(db_file: Path) -> list[str]:
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        return sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_migration_creates_tarefas_table_at_head_revision(data_dir: Path) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "tarefas" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_tarefas_table_has_no_derived_columns(data_dir: Path) -> None:
    """Only the raw fields and bookkeeping columns are stored."""
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {
            col["name"] for col in sa.inspect(engine).get_columns("tarefas")
        }
    finally:
        engine.dispose()

    expected = {
        "id",
        "titulo",
        "categoria",
        "prazo",
        "concluida",
        "created_at",
    }
    assert columns == expected


def test_insert_and_read_back_tarefa_with_only_required_titulo(
    data_dir: Path,
) -> None:
    run_migrations()

    with session_scope() as session:
        tarefa = Tarefa(titulo="X")
        session.add(tarefa)
        session.flush()
        session.refresh(tarefa)
        tarefa_id = tarefa.id

    with session_scope() as session:
        loaded = session.get(Tarefa, tarefa_id)
        assert loaded is not None
        assert loaded.titulo == "X"
        assert loaded.categoria is None
        assert loaded.prazo is None
        assert loaded.concluida is False
        assert loaded.created_at is not None
