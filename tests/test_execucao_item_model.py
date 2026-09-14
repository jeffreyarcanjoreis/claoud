"""Tests for the ExecucaoItem model and migration (0029_create_execucoes_item).

Covers the functional specification (issue 09):
- after migrating, the "execucoes_item" table exists and the database is
  stamped at the head revision ("0029");
- the table has exactly the expected columns -- no derived columns;
- inserting an ExecucaoItem with only the required fields round-trips, with
  the optional fields (carga_real, reps_real, observacao) as None and
  created_at populated by the server;
- the unique constraint on (treino_item_id, data) is enforced: a second row
  for the same item on the same date raises IntegrityError.

Isolation pattern shared with the other *_model.py suites: KAIROS_DATA_DIR
points at a temp dir and the cached engine is disposed on setup/teardown.
"""

import datetime
from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.db import session_scope
from kairos.execucao.models import ExecucaoItem
from kairos.migrations_runner import run_migrations
from kairos.treinos.models import Exercicio, Treino, TreinoItem

HEAD_REVISION = "0029"  # bumped by migration 0029_create_execucoes_item


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


def _columns(db_file: Path, table: str) -> set:
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        return {col["name"] for col in sa.inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def _create_treino_item(aluno_nome: str = "Marcos Vieira") -> int:
    """Create the chain aluno -> treino -> exercicio -> treino_item and
    return the treino_item's id, so tests can attach executions to it."""
    aluno = create_aluno(name=aluno_nome)

    with session_scope() as session:
        exercicio = Exercicio(nome="Agachamento")
        session.add(exercicio)
        session.flush()

        treino = Treino(aluno_id=aluno["id"], nome="Treino A")
        session.add(treino)
        session.flush()

        item = TreinoItem(treino_id=treino.id, exercicio_id=exercicio.id, ordem=1)
        session.add(item)
        session.flush()
        return item.id


def test_migration_creates_execucoes_item_table_at_head_revision(
    data_dir: Path,
) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        tables = sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()

    assert "execucoes_item" in tables
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_execucoes_item_table_has_expected_columns(data_dir: Path) -> None:
    run_migrations()
    db_file = data_dir / "kairos.db"

    assert _columns(db_file, "execucoes_item") == {
        "id",
        "treino_item_id",
        "data",
        "feito",
        "carga_real",
        "reps_real",
        "observacao",
        "created_at",
    }


def test_insert_and_read_back_execucao_item_with_only_required_fields(
    data_dir: Path,
) -> None:
    run_migrations()
    item_id = _create_treino_item()
    hoje = datetime.date.today()

    with session_scope() as session:
        execucao = ExecucaoItem(treino_item_id=item_id, data=hoje, feito=True)
        session.add(execucao)
        session.flush()
        session.refresh(execucao)
        execucao_id = execucao.id

    with session_scope() as session:
        loaded = session.get(ExecucaoItem, execucao_id)
        assert loaded is not None
        assert loaded.treino_item_id == item_id
        assert loaded.data == hoje
        assert loaded.feito is True
        assert loaded.carga_real is None
        assert loaded.reps_real is None
        assert loaded.observacao is None
        assert loaded.created_at is not None


def test_insert_and_read_back_execucao_item_with_all_fields(data_dir: Path) -> None:
    run_migrations()
    item_id = _create_treino_item()
    hoje = datetime.date.today()

    with session_scope() as session:
        execucao = ExecucaoItem(
            treino_item_id=item_id,
            data=hoje,
            feito=True,
            carga_real="20kg",
            reps_real="10",
            observacao="Fiz com dor leve no joelho.",
        )
        session.add(execucao)
        session.flush()
        session.refresh(execucao)
        execucao_id = execucao.id

    with session_scope() as session:
        loaded = session.get(ExecucaoItem, execucao_id)
        assert loaded is not None
        assert loaded.carga_real == "20kg"
        assert loaded.reps_real == "10"
        assert loaded.observacao == "Fiz com dor leve no joelho."


def test_unique_constraint_on_treino_item_id_and_data(data_dir: Path) -> None:
    run_migrations()
    item_id = _create_treino_item()
    hoje = datetime.date.today()

    with session_scope() as session:
        session.add(ExecucaoItem(treino_item_id=item_id, data=hoje, feito=True))
        session.flush()

    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.add(
                ExecucaoItem(treino_item_id=item_id, data=hoje, feito=False)
            )
            session.flush()


def test_unique_constraint_allows_same_item_on_different_dates(
    data_dir: Path,
) -> None:
    run_migrations()
    item_id = _create_treino_item()
    d1 = datetime.date(2026, 9, 1)
    d2 = datetime.date(2026, 9, 2)

    with session_scope() as session:
        session.add(ExecucaoItem(treino_item_id=item_id, data=d1, feito=True))
        session.add(ExecucaoItem(treino_item_id=item_id, data=d2, feito=False))
        session.flush()

    with session_scope() as session:
        rows = session.query(ExecucaoItem).filter_by(treino_item_id=item_id).all()
        assert len(rows) == 2
