"""Tests for the Contato model and migrations (0015_create_contatos,
0016_expand_contatos_perfil).

Covers the functional specification:
- after migrating, the "contatos" table exists and the database is stamped
  at the head revision ("0018", now that migration 0018_create_perfis
  is the newest one, applied on top of 0016 and 0017);
- the table has exactly the expected columns, INCLUDING the full student
  profile added by issue 22's native public sign-up form -- idade, sexo,
  objetivo, objetivos_secundarios, prazo_desejado, frequencia_desejada,
  condicoes, lesoes, medicamentos, nivel_condicionamento, consentimento and
  origem (health data is now legitimately stored here, gathered under the
  person's explicit consent -- see the `consentimento` field);
- inserting a Contato with only the required "nome" field works end to end:
  contato and observacao round-trip as None (never a fabricated default),
  status round-trips as "a_contatar" (the server default), consentimento
  round-trips as False (the server default -- absence of consent, never
  invented consent) and created_at is populated by the server;
- inserting a Contato with the full profile (including health fields and
  consentimento=True) round-trips every field.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from pathlib import Path
from typing import Optional

import pytest
import sqlalchemy as sa

import kairos.db
from kairos.contatos.models import Contato
from kairos.db import session_scope
from kairos.migrations_runner import run_migrations

HEAD_REVISION = "0024"  # bumped by migration 0024_create_reconhecimentos_nivel


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


def test_migration_creates_contatos_table_at_head_revision(data_dir: Path) -> None:
    run_migrations()

    db_file = data_dir / "kairos.db"
    assert db_file.exists()
    assert "contatos" in _table_names(db_file)
    assert _stamped_revision(db_file) == HEAD_REVISION


def test_contatos_table_has_the_full_sign_up_profile_columns(data_dir: Path) -> None:
    """Issue 22 expanded the table with the native public sign-up form's full
    student profile -- including health fields, now legitimately stored
    here under the person's explicit consent (`consentimento`)."""
    run_migrations()

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        columns = {
            col["name"] for col in sa.inspect(engine).get_columns("contatos")
        }
    finally:
        engine.dispose()

    expected = {
        "id",
        "nome",
        "contato",
        "status",
        "observacao",
        "idade",
        "sexo",
        "objetivo",
        "objetivos_secundarios",
        "prazo_desejado",
        "frequencia_desejada",
        "condicoes",
        "lesoes",
        "medicamentos",
        "nivel_condicionamento",
        "consentimento",
        "origem",
        "created_at",
    }
    assert columns == expected


def test_insert_and_read_back_contato_with_only_required_nome(
    data_dir: Path,
) -> None:
    run_migrations()

    with session_scope() as session:
        contato = Contato(nome="Ana Lima")
        session.add(contato)
        session.flush()
        session.refresh(contato)
        contato_id = contato.id

    with session_scope() as session:
        loaded = session.get(Contato, contato_id)
        assert loaded is not None
        assert loaded.nome == "Ana Lima"
        assert loaded.contato is None
        assert loaded.observacao is None
        assert loaded.status == "a_contatar"
        assert loaded.idade is None
        assert loaded.sexo is None
        assert loaded.objetivo is None
        assert loaded.objetivos_secundarios is None
        assert loaded.prazo_desejado is None
        assert loaded.frequencia_desejada is None
        assert loaded.condicoes is None
        assert loaded.lesoes is None
        assert loaded.medicamentos is None
        assert loaded.nivel_condicionamento is None
        assert loaded.consentimento is False
        assert loaded.origem is None
        assert loaded.created_at is not None


def test_insert_and_read_back_contato_with_full_sign_up_profile(
    data_dir: Path,
) -> None:
    run_migrations()

    with session_scope() as session:
        contato = Contato(
            nome="Beatriz Nunes",
            contato="beatriz@example.com",
            idade=34,
            sexo="feminino",
            objetivo="Emagrecimento",
            objetivos_secundarios="Condicionamento geral",
            prazo_desejado="3 meses",
            frequencia_desejada="3-4",
            condicoes="Hipertensão controlada",
            lesoes="Joelho direito",
            medicamentos="Losartana",
            nivel_condicionamento="iniciante",
            consentimento=True,
            origem="cadastro",
        )
        session.add(contato)
        session.flush()
        session.refresh(contato)
        contato_id = contato.id

    with session_scope() as session:
        loaded = session.get(Contato, contato_id)
        assert loaded is not None
        assert loaded.nome == "Beatriz Nunes"
        assert loaded.contato == "beatriz@example.com"
        assert loaded.idade == 34
        assert loaded.sexo == "feminino"
        assert loaded.objetivo == "Emagrecimento"
        assert loaded.objetivos_secundarios == "Condicionamento geral"
        assert loaded.prazo_desejado == "3 meses"
        assert loaded.frequencia_desejada == "3-4"
        assert loaded.condicoes == "Hipertensão controlada"
        assert loaded.lesoes == "Joelho direito"
        assert loaded.medicamentos == "Losartana"
        assert loaded.nivel_condicionamento == "iniciante"
        assert loaded.consentimento is True
        assert loaded.origem == "cadastro"
