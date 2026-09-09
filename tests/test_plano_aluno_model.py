"""Tests for the PlanoAluno model and migration (0012_create_planos_aluno).

Covers the functional specification:
- after migrating, the "planos_aluno" table exists and the database is
  stamped at the head revision ("0015");
- the table has exactly the expected columns -- no derived columns are
  stored;
- inserting a PlanoAluno linked to an existing Aluno works end to end:
  aluno_id, formato and the decimal valor round-trip correctly, and optional
  fields left unset (ciclo_meses, inicio, observacao) round-trip as None
  (never a fabricated default);
- at most one plan per student: inserting two PlanoAluno rows for the same
  aluno_id violates the unique constraint.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from decimal import Decimal
from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.db import session_scope
from kairos.financeiro.models import PlanoAluno
from kairos.migrations_runner import run_migrations

HEAD_REVISION = "0020"  # bumped by migration 0020_create_mensagens


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


def test_migration_creates_planos_aluno_table_at_head_revision(
    data_dir: Path,
) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "planos_aluno" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_planos_aluno_table_has_no_derived_columns(data_dir: Path) -> None:
    """Only the raw fields and bookkeeping columns are stored."""
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {
            col["name"] for col in sa.inspect(engine).get_columns("planos_aluno")
        }
    finally:
        engine.dispose()

    expected = {
        "id",
        "aluno_id",
        "formato",
        "valor",
        "ciclo_meses",
        "inicio",
        "observacao",
        "created_at",
    }
    assert columns == expected


def test_insert_and_read_back_plano_aluno_linked_to_aluno(data_dir: Path) -> None:
    run_migrations()

    aluno = create_aluno(name="Maria Silva")

    with session_scope() as session:
        plano = PlanoAluno(
            aluno_id=aluno["id"],
            formato="digital",
            valor=Decimal("120.00"),
        )
        session.add(plano)
        session.flush()
        session.refresh(plano)
        plano_id = plano.id

    with session_scope() as session:
        loaded = session.get(PlanoAluno, plano_id)
        assert loaded is not None
        assert loaded.aluno_id == aluno["id"]
        assert loaded.formato == "digital"
        assert loaded.valor == Decimal("120.00")
        assert loaded.ciclo_meses is None
        assert loaded.inicio is None
        assert loaded.observacao is None


def test_two_planos_for_same_aluno_violates_unique_constraint(
    data_dir: Path,
) -> None:
    run_migrations()

    aluno = create_aluno(name="Maria Silva")

    with session_scope() as session:
        session.add(
            PlanoAluno(
                aluno_id=aluno["id"],
                formato="digital",
                valor=Decimal("120.00"),
            )
        )
        session.flush()

    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.add(
                PlanoAluno(
                    aluno_id=aluno["id"],
                    formato="grupo",
                    valor=Decimal("80.00"),
                )
            )
            session.flush()
