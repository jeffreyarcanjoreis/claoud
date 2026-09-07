"""Tests for the Aluno "foto" field and migration (0005_add_foto_to_alunos).

Covers the functional specification:
- after migrating, the "alunos" table has a "foto" column and the database
  is stamped at the head revision ("0015");
- create_aluno() returns a dict whose "foto" key is None when no photo was
  supplied (architecture rule 6: no fabricated default);
- setting "foto" on a row and reading it back through get_aluno() returns
  the stored value.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa

import kairos.db
from kairos.alunos.models import Aluno
from kairos.alunos.service import create_aluno, get_aluno
from kairos.db import session_scope
from kairos.migrations_runner import run_migrations

HEAD_REVISION = "0019"  # bumped by migration 0019_add_email_to_alunos


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


def test_migration_adds_foto_column_to_alunos_at_head_revision(
    data_dir: Path,
) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()

    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {col["name"] for col in sa.inspect(engine).get_columns("alunos")}
    finally:
        engine.dispose()

    assert "foto" in columns
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_create_aluno_returns_foto_as_none_by_default(data_dir: Path) -> None:
    run_migrations()

    aluno = create_aluno(name="Maria Silva")

    assert aluno["foto"] is None


def test_setting_foto_on_a_row_round_trips_through_get_aluno(
    data_dir: Path,
) -> None:
    run_migrations()

    aluno = create_aluno(name="Joao Souza")
    assert aluno["foto"] is None

    with session_scope() as session:
        row = session.get(Aluno, aluno["id"])
        assert row is not None
        row.foto = "joao-souza.jpg"

    loaded = get_aluno(aluno["id"])
    assert loaded is not None
    assert loaded["foto"] == "joao-souza.jpg"
