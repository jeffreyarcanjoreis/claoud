"""Tests for the SessaoAgendada model and migration (0006_create_sessoes_agendadas).

Covers the functional specification:
- after migrating, the "sessoes_agendadas" table exists and the database is
  stamped at the head revision ("0015");
- the table has exactly the expected columns -- no derived columns are
  stored;
- inserting a SessaoAgendada linked to an existing Aluno works end to end:
  aluno_id, data, hora and tipo round-trip correctly, and optional fields
  left unset (duracao_min, observacao) round-trip as None (never a
  fabricated default).

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

import datetime
from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa

import kairos.db
from kairos.agenda.models import SessaoAgendada
from kairos.alunos.service import create_aluno
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


def test_migration_creates_sessoes_agendadas_table_at_head_revision(
    data_dir: Path,
) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "sessoes_agendadas" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_sessoes_agendadas_table_has_no_derived_columns(data_dir: Path) -> None:
    """Only the raw fields and bookkeeping columns are stored."""
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {
            col["name"] for col in sa.inspect(engine).get_columns("sessoes_agendadas")
        }
    finally:
        engine.dispose()

    expected = {
        "id",
        "aluno_id",
        "data",
        "hora",
        "duracao_min",
        "tipo",
        "observacao",
        "treino_id",
        "created_at",
    }
    assert columns == expected


def test_insert_and_read_back_sessao_agendada_linked_to_aluno(
    data_dir: Path,
) -> None:
    run_migrations()

    aluno = create_aluno(name="Maria Silva")

    with session_scope() as session:
        sessao = SessaoAgendada(
            aluno_id=aluno["id"],
            data=datetime.date(2026, 9, 1),
            hora=datetime.time(9, 0),
            tipo="individual",
            duracao_min=None,
            observacao=None,
        )
        session.add(sessao)
        session.flush()
        session.refresh(sessao)
        sessao_id = sessao.id

    with session_scope() as session:
        loaded = session.get(SessaoAgendada, sessao_id)
        assert loaded is not None
        assert loaded.aluno_id == aluno["id"]
        assert loaded.data == datetime.date(2026, 9, 1)
        assert loaded.hora == datetime.time(9, 0)
        assert loaded.tipo == "individual"
        assert loaded.duracao_min is None
        assert loaded.observacao is None
