"""Tests for issue 14: coach's task list ("Tarefas") on the Início page.

Covers the functional specification:
- service layer: a title is required (blank -> ValidationError); an invalid
  category is refused; an invalid deadline is refused; an empty category
  normalizes to None (never a fake default); a valid task is persisted and
  shows up in list_tarefas_abertas; concluir_tarefa removes a task from the
  open list; open tasks are ordered by deadline ascending, tasks without a
  deadline last, tie-broken by creation order;
- Início/routes: GET / shows the "Tarefas" section (with the add form) and,
  with no open tasks, the empty state ("Nenhuma tarefa em aberto."); POST
  /tarefas with a valid title redirects (303) to / and the new task shows up
  there; POST /tarefas without a title returns 400 with the error message and
  preserves what was typed; POST /tarefas/{id}/concluir and
  POST /tarefas/{id}/remover redirect (303) and the task disappears from
  GET /; concluding or removing a non-existent id returns 404.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.main import app
from kairos.tarefas.service import (
    ValidationError,
    concluir_tarefa,
    create_tarefa,
    list_tarefas_abertas,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------


def test_create_tarefa_without_titulo_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_tarefa(titulo=None)

        with pytest.raises(ValidationError):
            create_tarefa(titulo="   ")


def test_create_tarefa_with_invalid_categoria_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_tarefa(titulo="Ligar para aluno", categoria="xpto")


def test_create_tarefa_with_invalid_prazo_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_tarefa(titulo="Ligar para aluno", prazo="31/13/2026")

        with pytest.raises(ValidationError):
            create_tarefa(titulo="Ligar para aluno", prazo="abc")


def test_create_tarefa_with_empty_categoria_saves_none(data_dir: Path) -> None:
    with TestClient(app):
        tarefa = create_tarefa(titulo="Ligar para aluno", categoria="")

    assert tarefa["categoria"] is None


def test_create_valid_tarefa_persists_and_appears_in_open_list(
    data_dir: Path,
) -> None:
    with TestClient(app):
        create_tarefa(
            titulo="Publicar reels da semana",
            categoria="publicacao",
            prazo="2026-09-01",
        )

        abertas = list_tarefas_abertas()

    assert len(abertas) == 1
    assert abertas[0]["titulo"] == "Publicar reels da semana"
    assert abertas[0]["categoria"] == "publicacao"
    assert abertas[0]["prazo"].isoformat() == "2026-09-01"
    assert abertas[0]["concluida"] is False


def test_concluir_tarefa_removes_it_from_open_list(data_dir: Path) -> None:
    with TestClient(app):
        tarefa = create_tarefa(titulo="Enviar contrato")

        assert len(list_tarefas_abertas()) == 1

        result = concluir_tarefa(tarefa["id"])

        assert result is True
        assert list_tarefas_abertas() == []


def test_open_tasks_are_ordered_by_prazo_ascending_nulls_last(
    data_dir: Path,
) -> None:
    with TestClient(app):
        create_tarefa(titulo="Prazo dia 10", prazo="2026-09-10")
        create_tarefa(titulo="Prazo dia 01", prazo="2026-09-01")
        create_tarefa(titulo="Sem prazo")

        abertas = list_tarefas_abertas()

    titulos = [t["titulo"] for t in abertas]
    assert titulos == ["Prazo dia 01", "Prazo dia 10", "Sem prazo"]


# ---------------------------------------------------------------------------
# Início / routes
# ---------------------------------------------------------------------------


def test_inicio_shows_tarefas_section_and_add_form(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    text = response.text
    assert "Tarefas" in text
    assert 'name="titulo"' in text


def test_inicio_shows_empty_state_when_no_open_tasks(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Nenhuma tarefa em aberto." in response.text


def test_post_tarefas_valid_redirects_and_appears_on_inicio(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tarefas",
            data={"titulo": "Comprar equipamento", "categoria": "", "prazo": ""},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        follow_up = client.get("/")

    assert "Comprar equipamento" in follow_up.text


def test_post_tarefas_without_titulo_returns_400_and_preserves_input(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tarefas",
            data={
                "titulo": "",
                "categoria": "lembrete",
                "prazo": "2026-09-01",
            },
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Título é obrigatório." in response.text
    assert "2026-09-01" in response.text


def test_post_tarefas_concluir_redirects_and_removes_from_inicio(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        tarefa = create_tarefa(titulo="Tarefa a concluir")

        response = client.post(
            f"/tarefas/{tarefa['id']}/concluir", follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        follow_up = client.get("/")

    assert "Tarefa a concluir" not in follow_up.text


def test_post_tarefas_remover_redirects_and_removes_from_inicio(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        tarefa = create_tarefa(titulo="Tarefa a remover")

        response = client.post(
            f"/tarefas/{tarefa['id']}/remover", follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        follow_up = client.get("/")

    assert "Tarefa a remover" not in follow_up.text


def test_post_tarefas_concluir_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/tarefas/9999/concluir", follow_redirects=False)

    assert response.status_code == 404


def test_post_tarefas_remover_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/tarefas/9999/remover", follow_redirects=False)

    assert response.status_code == 404
