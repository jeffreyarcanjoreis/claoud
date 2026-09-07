"""Tests for the Treino/TreinoItem models and migration (0008_create_treinos).

Covers:
- after migrating, the "treinos" and "treino_itens" tables exist and the
  database is stamped at the head revision ("0015");
- each table has exactly the expected columns -- no derived columns;
- inserting a Treino with a TreinoItem round-trips, and optional prescription
  fields left unset (series, reps, carga, observacao) round-trip as None.

Isolation pattern shared with the other suites.
"""

from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.db import session_scope
from kairos.migrations_runner import run_migrations
from kairos.treinos.models import Exercicio, Treino, TreinoItem

HEAD_REVISION = "0019"  # bumped by migration 0019_add_email_to_alunos


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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


def _columns(db_file: Path, table: str) -> set:
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        return {col["name"] for col in sa.inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


def test_migration_creates_treino_tables_at_head_revision(data_dir: Path) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        tables = sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()

    assert "treinos" in tables
    assert "treino_itens" in tables
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_treino_tables_have_expected_columns(data_dir: Path) -> None:
    run_migrations()
    db_file = data_dir / "kairos.db"

    assert _columns(db_file, "treinos") == {
        "id",
        "aluno_id",
        "nome",
        "observacao",
        "created_at",
    }
    assert _columns(db_file, "treino_itens") == {
        "id",
        "treino_id",
        "exercicio_id",
        "ordem",
        "series",
        "reps",
        "carga",
        "observacao",
    }


def test_insert_and_read_back_treino_with_item(data_dir: Path) -> None:
    run_migrations()

    aluno = create_aluno(name="João Treino")

    with session_scope() as session:
        exercicio = Exercicio(nome="Agachamento")
        session.add(exercicio)
        session.flush()

        treino = Treino(aluno_id=aluno["id"], nome="Treino A")
        session.add(treino)
        session.flush()

        item = TreinoItem(
            treino_id=treino.id,
            exercicio_id=exercicio.id,
            ordem=1,
        )
        session.add(item)
        session.flush()
        item_id = item.id

    with session_scope() as session:
        loaded = session.get(TreinoItem, item_id)
        assert loaded is not None
        assert loaded.ordem == 1
        assert loaded.series is None
        assert loaded.reps is None
        assert loaded.carga is None
        assert loaded.observacao is None
