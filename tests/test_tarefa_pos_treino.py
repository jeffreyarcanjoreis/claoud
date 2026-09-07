"""Tests for issue 25 (Parte A): the automatic "Contatar <aluno>" task
created whenever a session is scheduled.

Covers the functional specification:
- ``create_sessao`` creates, as a side effect, a Tarefa with
  ``titulo=f"Contatar {nome do aluno}"``, ``categoria="contato"`` and
  ``prazo`` equal to the session's date plus one day;
- the automatic task shows up in ``list_tarefas_abertas``;
- scheduling two sessions creates two separate contact tasks;
- the automation is not tied to having a treino: a session without a
  ``treino_id`` still creates its contact task.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

import datetime
from pathlib import Path

import pytest

import kairos.db
from kairos.agenda.service import create_sessao
from kairos.alunos.service import create_aluno
from kairos.migrations_runner import run_migrations
from kairos.tarefas.service import list_tarefas_abertas


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    run_migrations()
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


@pytest.fixture
def aluno(data_dir: Path) -> dict:
    """Create a supporting Aluno and return its saved fields."""
    return create_aluno(name="Maria Silva")


def test_create_sessao_creates_one_open_contact_task(aluno: dict) -> None:
    sessao_data = "2026-01-10"

    create_sessao(
        aluno["id"], data=sessao_data, hora="08:00", tipo="individual"
    )

    tarefas = list_tarefas_abertas()
    assert len(tarefas) == 1
    tarefa = tarefas[0]
    assert tarefa["titulo"] == "Contatar Maria Silva"
    assert tarefa["categoria"] == "contato"
    assert tarefa["prazo"] == datetime.date(2026, 1, 11)
    assert tarefa["concluida"] is False


def test_scheduling_two_sessions_creates_two_contact_tasks(aluno: dict) -> None:
    create_sessao(aluno["id"], data="2026-02-01", hora="08:00", tipo="individual")
    create_sessao(aluno["id"], data="2026-02-03", hora="09:00", tipo="grupo")

    tarefas = list_tarefas_abertas()
    assert len(tarefas) == 2

    prazos = {t["prazo"] for t in tarefas}
    assert prazos == {datetime.date(2026, 2, 2), datetime.date(2026, 2, 4)}
    for tarefa in tarefas:
        assert tarefa["titulo"] == "Contatar Maria Silva"
        assert tarefa["categoria"] == "contato"


def test_session_without_treino_id_still_creates_the_contact_task(
    aluno: dict,
) -> None:
    sessao = create_sessao(
        aluno["id"], data="2026-03-05", hora="18:00", tipo="individual"
    )

    assert sessao["treino_id"] is None

    tarefas = list_tarefas_abertas()
    assert len(tarefas) == 1
    assert tarefas[0]["titulo"] == "Contatar Maria Silva"
    assert tarefas[0]["categoria"] == "contato"
    assert tarefas[0]["prazo"] == datetime.date(2026, 3, 6)
