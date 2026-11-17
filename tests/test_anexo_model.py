"""Tests for the AnexoExecucao model and migration (0030_create_anexos_execucao).

Covers the functional specification (issue 11):
- after migrating, the "anexos_execucao" table exists and the database is
  stamped at the head revision ("0030");
- the table has exactly the expected columns and an index on treino_item_id;
- inserting an AnexoExecucao with only the required fields round-trips, with
  observacao as None and created_at populated by the server.
"""

from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.db import session_scope
from kairos.execucao.models import AnexoExecucao
from kairos.migrations_runner import run_migrations
from kairos.treinos.models import Exercicio, Treino, TreinoItem

HEAD_REVISION = "0030"  # bumped by migration 0030_create_anexos_execucao


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


def _inspect(db_file: Path, fn):
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        return fn(sa.inspect(engine))
    finally:
        engine.dispose()


def _create_treino_item() -> int:
    aluno = create_aluno(name="Marcos Vieira")
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


def test_migration_creates_anexos_execucao_table_at_head_revision(
    data_dir: Path,
) -> None:
    run_migrations()
    db_file = data_dir / "kairos.db"

    tables = _inspect(db_file, lambda i: i.get_table_names())

    assert "anexos_execucao" in tables
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_anexos_execucao_table_has_expected_columns(data_dir: Path) -> None:
    run_migrations()
    db_file = data_dir / "kairos.db"

    cols = _inspect(db_file, lambda i: {c["name"] for c in i.get_columns("anexos_execucao")})

    assert cols == {
        "id",
        "treino_item_id",
        "filename",
        "tipo",
        "observacao",
        "created_at",
    }


def test_anexos_execucao_has_index_on_treino_item_id(data_dir: Path) -> None:
    run_migrations()
    db_file = data_dir / "kairos.db"

    indexes = _inspect(db_file, lambda i: i.get_indexes("anexos_execucao"))

    assert any(ix["column_names"] == ["treino_item_id"] for ix in indexes)


def test_insert_and_read_back_anexo_with_only_required_fields(
    data_dir: Path,
) -> None:
    run_migrations()
    item_id = _create_treino_item()

    with session_scope() as session:
        anexo = AnexoExecucao(
            treino_item_id=item_id, filename="abc123.png", tipo="imagem"
        )
        session.add(anexo)
        session.flush()
        session.refresh(anexo)
        anexo_id = anexo.id

    with session_scope() as session:
        loaded = session.get(AnexoExecucao, anexo_id)
        assert loaded is not None
        assert loaded.treino_item_id == item_id
        assert loaded.filename == "abc123.png"
        assert loaded.tipo == "imagem"
        assert loaded.observacao is None
        assert loaded.created_at is not None


def test_insert_and_read_back_anexo_with_observacao(data_dir: Path) -> None:
    run_migrations()
    item_id = _create_treino_item()

    with session_scope() as session:
        anexo = AnexoExecucao(
            treino_item_id=item_id,
            filename="abc123.mp4",
            tipo="video",
            observacao="Olhem meu joelho",
        )
        session.add(anexo)
        session.flush()
        anexo_id = anexo.id

    with session_scope() as session:
        loaded = session.get(AnexoExecucao, anexo_id)
        assert loaded.tipo == "video"
        assert loaded.observacao == "Olhem meu joelho"
