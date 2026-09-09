"""Tests for the Aluno model and migrations (0002_create_alunos,
0005_add_foto_to_alunos, 0017_expand_alunos_perfil, 0019_add_email_to_alunos).

Covers the functional specification (issues 23 and 29):
- after migrating, the "alunos" table exists and the database is stamped at
  the head revision ("0020");
- the table has exactly the expected columns, INCLUDING the profile fields
  added by issue 23 to carry a converted lead's full profile -- contact,
  sex, age_reported, weekly_frequency, conditioning_level, health_conditions
  and medications -- and the "email" column added by issue 29;
- inserting an Aluno with only the required "name" field works end to end:
  every new column round-trips as None (never a fabricated default);
- inserting an Aluno with the full expanded profile round-trips every new
  field, including the integer age_reported.

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


def test_migration_creates_alunos_table_at_head_revision(data_dir: Path) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "alunos" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_alunos_table_has_the_expanded_profile_columns(data_dir: Path) -> None:
    """Issue 23 expanded the table with the profile carried over from a
    converted lead (contatos), so a lead's full profile survives conversion
    into a student."""
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {col["name"] for col in sa.inspect(engine).get_columns("alunos")}
    finally:
        engine.dispose()

    expected = {
        "id",
        "name",
        "birth_date",
        "objective",
        "phase",
        "plan_start",
        "plan_end",
        "restrictions",
        "alert",
        "contact",
        "email",
        "sex",
        "age_reported",
        "weekly_frequency",
        "conditioning_level",
        "health_conditions",
        "medications",
        "status",
        "notes",
        "foto",
        "created_at",
    }
    assert columns == expected


def test_insert_and_read_back_aluno_with_only_required_name(data_dir: Path) -> None:
    run_migrations()

    with session_scope() as session:
        aluno = Aluno(name="Maria Silva")
        session.add(aluno)
        session.flush()
        session.refresh(aluno)
        aluno_id = aluno.id

    with session_scope() as session:
        loaded = session.get(Aluno, aluno_id)
        assert loaded is not None
        assert loaded.name == "Maria Silva"
        assert loaded.contact is None
        assert loaded.sex is None
        assert loaded.age_reported is None
        assert loaded.weekly_frequency is None
        assert loaded.conditioning_level is None
        assert loaded.health_conditions is None
        assert loaded.medications is None
        assert loaded.status == "active"
        assert loaded.created_at is not None


def test_insert_and_read_back_aluno_with_full_expanded_profile(
    data_dir: Path,
) -> None:
    run_migrations()

    with session_scope() as session:
        aluno = Aluno(
            name="Beatriz Nunes",
            contact="beatriz@example.com",
            sex="feminino",
            age_reported=34,
            weekly_frequency="3-4",
            conditioning_level="iniciante",
            health_conditions="Hipertensão controlada",
            medications="Losartana",
            restrictions="Joelho direito",
        )
        session.add(aluno)
        session.flush()
        session.refresh(aluno)
        aluno_id = aluno.id

    with session_scope() as session:
        loaded = session.get(Aluno, aluno_id)
        assert loaded is not None
        assert loaded.name == "Beatriz Nunes"
        assert loaded.contact == "beatriz@example.com"
        assert loaded.sex == "feminino"
        assert loaded.age_reported == 34
        assert loaded.weekly_frequency == "3-4"
        assert loaded.conditioning_level == "iniciante"
        assert loaded.health_conditions == "Hipertensão controlada"
        assert loaded.medications == "Losartana"
        assert loaded.restrictions == "Joelho direito"
