"""Tests for the Perfil model and migration (0018_create_perfis).

Covers the functional specification (issue 26, Fase 1):
- after migrating, the "perfis" table exists and the database is stamped at
  the head revision ("0020");
- the table has exactly the expected columns -- no derived columns are
  stored;
- inserting a Perfil with only the required "user_id"/"papel" fields works
  end to end: aluno_id round-trips as None (never a fabricated default), and
  created_at is populated by the server;
- inserting a Perfil with an aluno_id round-trips it;
- user_id is unique: inserting a second Perfil with the same user_id fails.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

import kairos.db
from kairos.auth.models import Perfil
from kairos.db import session_scope
from kairos.migrations_runner import run_migrations

HEAD_REVISION = "0021"  # bumped by migration 0021_create_checkins


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


def test_migration_creates_perfis_table_at_head_revision(data_dir: Path) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "perfis" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_perfis_table_has_no_derived_columns(data_dir: Path) -> None:
    """Only the raw fields and bookkeeping columns are stored."""
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {col["name"] for col in sa.inspect(engine).get_columns("perfis")}
    finally:
        engine.dispose()

    expected = {"id", "user_id", "papel", "aluno_id", "created_at"}
    assert columns == expected


def test_insert_and_read_back_perfil_with_only_required_fields(
    data_dir: Path,
) -> None:
    run_migrations()

    with session_scope() as session:
        perfil = Perfil(user_id="u-1", papel="coach")
        session.add(perfil)
        session.flush()
        session.refresh(perfil)
        perfil_id = perfil.id

    with session_scope() as session:
        loaded = session.get(Perfil, perfil_id)
        assert loaded is not None
        assert loaded.user_id == "u-1"
        assert loaded.papel == "coach"
        assert loaded.aluno_id is None
        assert loaded.created_at is not None


def test_insert_and_read_back_perfil_with_aluno_id(data_dir: Path) -> None:
    run_migrations()

    from kairos.alunos.models import Aluno

    with session_scope() as session:
        aluno = Aluno(name="Maria Silva")
        session.add(aluno)
        session.flush()
        session.refresh(aluno)
        aluno_id = aluno.id

    with session_scope() as session:
        perfil = Perfil(user_id="u-2", papel="aluno", aluno_id=aluno_id)
        session.add(perfil)
        session.flush()
        session.refresh(perfil)
        perfil_id = perfil.id

    with session_scope() as session:
        loaded = session.get(Perfil, perfil_id)
        assert loaded is not None
        assert loaded.papel == "aluno"
        assert loaded.aluno_id == aluno_id


def test_user_id_is_unique(data_dir: Path) -> None:
    run_migrations()

    with session_scope() as session:
        session.add(Perfil(user_id="dup", papel="coach"))
        session.flush()

    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.add(Perfil(user_id="dup", papel="aluno"))
            session.flush()
