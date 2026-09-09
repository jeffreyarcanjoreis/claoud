"""Tests for the Despesa model and migration (0014_create_despesas).

Covers the functional specification:
- after migrating, the "despesas" table exists and the database is stamped
  at the head revision ("0015");
- the table has exactly the expected columns -- no derived columns are
  stored;
- inserting a Despesa works end to end: data, descricao and the decimal
  valor round-trip correctly, and optional fields left unset (categoria,
  observacao) round-trip as None (never a fabricated default).

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
from kairos.db import session_scope
from kairos.financeiro.models import Despesa
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


def test_migration_creates_despesas_table_at_head_revision(data_dir: Path) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "despesas" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_despesas_table_has_no_derived_columns(data_dir: Path) -> None:
    """Only the raw fields and bookkeeping columns are stored."""
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {col["name"] for col in sa.inspect(engine).get_columns("despesas")}
    finally:
        engine.dispose()

    expected = {
        "id",
        "data",
        "descricao",
        "categoria",
        "valor",
        "observacao",
        "created_at",
    }
    assert columns == expected


def test_insert_and_read_back_despesa(data_dir: Path) -> None:
    run_migrations()

    with session_scope() as session:
        despesa = Despesa(
            data=datetime.date(2026, 8, 10),
            descricao="Aluguel",
            valor=Decimal("800.00"),
        )
        session.add(despesa)
        session.flush()
        session.refresh(despesa)
        despesa_id = despesa.id

    with session_scope() as session:
        loaded = session.get(Despesa, despesa_id)
        assert loaded is not None
        assert loaded.data == datetime.date(2026, 8, 10)
        assert loaded.descricao == "Aluguel"
        assert loaded.valor == Decimal("800.00")
        assert loaded.categoria is None
        assert loaded.observacao is None
