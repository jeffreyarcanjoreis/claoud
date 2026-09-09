"""Tests for the Perimetria model and migration (0004_create_perimetrias).

Covers the functional specification:
- after migrating, the "perimetrias" table exists and the database is
  stamped at the head revision ("0015");
- inserting a Perimetria linked to an existing Avaliacao (which is itself
  linked to an existing Aluno) works end to end: avaliacao_id, segmento and
  the decimal valor round-trip correctly;
- no derived columns exist on the table -- only id, avaliacao_id, segmento
  and valor are stored;
- at most one measurement per segment per assessment: inserting two
  Perimetrias with the same (avaliacao_id, segmento) pair violates the
  unique constraint.

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
from kairos.avaliacoes.models import Perimetria
from kairos.avaliacoes.service import create_avaliacao
from kairos.db import session_scope
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


def _create_avaliacao_for_new_aluno(name: str = "Maria Silva") -> int:
    """Create an Aluno and an Avaliacao for it, returning the avaliacao id."""
    aluno = create_aluno(name=name)
    avaliacao = create_avaliacao(aluno["id"], data="2026-01-15")
    return avaliacao["id"]


def test_migration_creates_perimetrias_table_at_head_revision(
    data_dir: Path,
) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "perimetrias" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_perimetrias_table_has_no_derived_columns(data_dir: Path) -> None:
    """No delta column is stored: derived values are computed on demand."""
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {
            col["name"] for col in sa.inspect(engine).get_columns("perimetrias")
        }
    finally:
        engine.dispose()

    expected = {"id", "avaliacao_id", "segmento", "valor"}
    assert columns == expected


def test_insert_and_read_back_perimetria_linked_to_avaliacao(
    data_dir: Path,
) -> None:
    run_migrations()

    avaliacao_id = _create_avaliacao_for_new_aluno()

    with session_scope() as session:
        perimetria = Perimetria(
            avaliacao_id=avaliacao_id,
            segmento="Cintura",
            valor=Decimal("82.5"),
        )
        session.add(perimetria)
        session.flush()
        session.refresh(perimetria)
        perimetria_id = perimetria.id

    with session_scope() as session:
        loaded = session.get(Perimetria, perimetria_id)
        assert loaded is not None
        assert loaded.avaliacao_id == avaliacao_id
        assert loaded.segmento == "Cintura"
        assert loaded.valor == Decimal("82.5")


def test_two_perimetrias_same_avaliacao_and_segmento_violates_unique_constraint(
    data_dir: Path,
) -> None:
    run_migrations()

    avaliacao_id = _create_avaliacao_for_new_aluno()

    with session_scope() as session:
        session.add(
            Perimetria(
                avaliacao_id=avaliacao_id,
                segmento="Cintura",
                valor=Decimal("82.5"),
            )
        )
        session.flush()

    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.add(
                Perimetria(
                    avaliacao_id=avaliacao_id,
                    segmento="Cintura",
                    valor=Decimal("83.0"),
                )
            )
            session.flush()
