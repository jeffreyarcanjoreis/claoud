"""Tests for issue 01: Avaliacao model and migration.

Covers the functional specification:
- after startup, the "avaliacoes" table exists and the database is stamped
  at the head revision ("0015");
- inserting an Avaliacao linked to an existing Aluno works end to end: the
  aluno_id foreign key round-trips, decimal metrics (peso, altura,
  gordura_pct, massa_magra, massa_gorda) round-trip with their values, and
  metrics left unset round-trip as None (never a fabricated default);
- no derived columns (delta, IMC) exist on the table -- only the raw
  measurements and bookkeeping columns are stored.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.avaliacoes.models import Avaliacao
from kairos.db import session_scope
from kairos.migrations_runner import run_migrations

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


def test_migration_creates_avaliacoes_table_at_head_revision(data_dir: Path) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "avaliacoes" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_avaliacoes_table_has_no_derived_columns(data_dir: Path) -> None:
    """No delta/IMC column is stored: derived values are computed on demand."""
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {col["name"] for col in sa.inspect(engine).get_columns("avaliacoes")}
    finally:
        engine.dispose()

    expected = {
        "id",
        "aluno_id",
        "data",
        "peso",
        "altura",
        "gordura_pct",
        "massa_magra",
        "massa_gorda",
        "created_at",
    }
    assert columns == expected


def test_insert_and_read_back_avaliacao_linked_to_aluno(data_dir: Path) -> None:
    run_migrations()

    aluno = create_aluno(name="Maria Silva")

    with session_scope() as session:
        avaliacao = Avaliacao(
            aluno_id=aluno["id"],
            data=datetime.date(2026, 1, 15),
            peso=Decimal("72.35"),
            altura=Decimal("168.50"),
            gordura_pct=Decimal("24.7"),
            massa_magra=Decimal("54.10"),
            massa_gorda=Decimal("18.25"),
        )
        session.add(avaliacao)
        session.flush()
        session.refresh(avaliacao)
        avaliacao_id = avaliacao.id

    with session_scope() as session:
        loaded = session.get(Avaliacao, avaliacao_id)
        assert loaded is not None
        assert loaded.aluno_id == aluno["id"]
        assert loaded.data == datetime.date(2026, 1, 15)
        assert loaded.peso == Decimal("72.35")
        assert loaded.altura == Decimal("168.50")
        assert loaded.gordura_pct == Decimal("24.7")
        assert loaded.massa_magra == Decimal("54.10")
        assert loaded.massa_gorda == Decimal("18.25")
        assert loaded.created_at is not None


def test_insert_avaliacao_with_null_metrics_round_trips_as_none(
    data_dir: Path,
) -> None:
    run_migrations()

    aluno = create_aluno(name="Joao Souza")

    with session_scope() as session:
        avaliacao = Avaliacao(
            aluno_id=aluno["id"],
            data=datetime.date(2026, 2, 1),
            peso=Decimal("80.00"),
            altura=None,
            gordura_pct=None,
            massa_magra=None,
            massa_gorda=None,
        )
        session.add(avaliacao)
        session.flush()
        session.refresh(avaliacao)
        avaliacao_id = avaliacao.id

    with session_scope() as session:
        loaded = session.get(Avaliacao, avaliacao_id)
        assert loaded is not None
        assert loaded.peso == Decimal("80.00")
        assert loaded.altura is None
        assert loaded.gordura_pct is None
        assert loaded.massa_magra is None
        assert loaded.massa_gorda is None


def test_insert_avaliacao_with_nonexistent_aluno_id(data_dir: Path) -> None:
    """SQLite does not enforce foreign keys by default, so this only checks
    that the insert/read round-trip works; FK rejection is not asserted.
    """
    run_migrations()

    with session_scope() as session:
        avaliacao = Avaliacao(
            aluno_id=999999,
            data=datetime.date(2026, 3, 1),
            peso=Decimal("65.00"),
        )
        session.add(avaliacao)
        session.flush()
        session.refresh(avaliacao)
        avaliacao_id = avaliacao.id

    with session_scope() as session:
        loaded = session.get(Avaliacao, avaliacao_id)
        assert loaded is not None
        assert loaded.aluno_id == 999999
