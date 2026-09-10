"""Tests for the Exercicio model and migration (0007_create_exercicios).

Covers:
- after migrating, the "exercicios" table exists and the database is stamped
  at the head revision ("0015");
- the table has exactly the expected columns -- no derived columns are stored;
- inserting an Exercicio round-trips: nome persists, and optional fields left
  unset (grupo_muscular, observacao) round-trip as None (never a fabricated
  default).

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and the
SQLite file is not kept open on Windows.
"""

from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa

import kairos.db
from kairos.db import session_scope
from kairos.migrations_runner import run_migrations
from kairos.treinos.models import Exercicio

HEAD_REVISION = "0023"  # bumped by migration 0023_add_frente_to_alunos


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def _stamped_revision(db_file: Path) -> Optional[str]:
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


def test_migration_creates_exercicios_table_at_head_revision(data_dir: Path) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "exercicios" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_exercicios_table_has_no_derived_columns(data_dir: Path) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {col["name"] for col in sa.inspect(engine).get_columns("exercicios")}
    finally:
        engine.dispose()

    assert columns == {"id", "nome", "grupo_muscular", "observacao", "created_at"}


def test_insert_and_read_back_exercicio(data_dir: Path) -> None:
    run_migrations()

    with session_scope() as session:
        exercicio = Exercicio(nome="Agachamento livre", grupo_muscular=None, observacao=None)
        session.add(exercicio)
        session.flush()
        session.refresh(exercicio)
        exercicio_id = exercicio.id

    with session_scope() as session:
        loaded = session.get(Exercicio, exercicio_id)
        assert loaded is not None
        assert loaded.nome == "Agachamento livre"
        assert loaded.grupo_muscular is None
        assert loaded.observacao is None
        assert loaded.created_at is not None
