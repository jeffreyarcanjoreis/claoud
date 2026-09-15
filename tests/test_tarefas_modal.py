"""Tests for issue 28: the Início's "Tarefas" section opens in a modal, with
AJAX actions (content-negotiated JSON) and a server-rendered list fragment.

Covers the functional specification:
- POST /tarefas, POST /tarefas/{id}/concluir and POST /tarefas/{id}/remover
  respond with JSON when the request signals it wants JSON (Accept:
  application/json or X-Requested-With: fetch/XMLHttpRequest): success is
  {"ok": true}; creating without a title is a 400 with {"ok": false,
  "error": <non-empty message>}; concluding/removing an unknown id is a 404
  with {"ok": false, "error": <non-empty message>}.
- Without those headers, the old plain-HTML behavior is untouched: 303
  redirect to "/" on success, HTML re-render on the creation error, and a 404
  HTML page for an unknown id.
- GET /tarefas/fragmento renders just the open tasks list partial (no panel
  shell) — the created task's title and the ".tarefa-card" class show up
  when there's an open task; the empty state ("Nenhuma tarefa" /
  "tarefas-vazio") shows up when there are none.
- GET / (Início) contains the tasks modal (".v-modal-tarefas" /
  "id=\"tarefas-modal\""), the "#tarefas-toggle" checkbox, the
  "#tarefa-add-form" add form and the "#tarefas-lista-container" wrapper.

Same isolation pattern as tests/test_tarefas.py: KAIROS_DATA_DIR points at a
temp dir and the cached engine is disposed on teardown. Authentication is
handled by the autouse `_auto_login_as_coach` fixture in conftest.py.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.main import app
from kairos.tarefas.service import create_tarefa

AJAX_HEADERS = {"Accept": "application/json"}


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# POST /tarefas — JSON (AJAX) path
# ---------------------------------------------------------------------------


def test_post_tarefas_json_valid_returns_ok_true_and_persists(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tarefas",
            data={"titulo": "Ligar para aluno", "categoria": "", "prazo": ""},
            headers=AJAX_HEADERS,
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        fragmento = client.get("/tarefas/fragmento")

    assert "Ligar para aluno" in fragmento.text


def test_post_tarefas_json_without_titulo_returns_400_with_error(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tarefas",
            data={"titulo": "", "categoria": "", "prazo": ""},
            headers=AJAX_HEADERS,
        )

    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["error"]  # non-empty message


def test_post_tarefas_json_accepts_x_requested_with_fetch(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tarefas",
            data={"titulo": "Enviar orçamento", "categoria": "", "prazo": ""},
            headers={"X-Requested-With": "fetch"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# POST /tarefas/{id}/concluir and /remover — JSON (AJAX) path
# ---------------------------------------------------------------------------


def test_post_tarefas_concluir_json_returns_ok_true_and_disappears(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        tarefa = create_tarefa(titulo="Tarefa a concluir via AJAX")

        response = client.post(
            f"/tarefas/{tarefa['id']}/concluir", headers=AJAX_HEADERS
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        fragmento = client.get("/tarefas/fragmento")

    assert "Tarefa a concluir via AJAX" not in fragmento.text


def test_post_tarefas_remover_json_returns_ok_true_and_disappears(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        tarefa = create_tarefa(titulo="Tarefa a remover via AJAX")

        response = client.post(
            f"/tarefas/{tarefa['id']}/remover", headers=AJAX_HEADERS
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        fragmento = client.get("/tarefas/fragmento")

    assert "Tarefa a remover via AJAX" not in fragmento.text


def test_post_tarefas_concluir_json_unknown_id_returns_404_with_error(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post("/tarefas/9999/concluir", headers=AJAX_HEADERS)

    assert response.status_code == 404
    body = response.json()
    assert body["ok"] is False
    assert body["error"]  # non-empty message


def test_post_tarefas_remover_json_unknown_id_returns_404_with_error(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post("/tarefas/9999/remover", headers=AJAX_HEADERS)

    assert response.status_code == 404
    body = response.json()
    assert body["ok"] is False
    assert body["error"]  # non-empty message


# ---------------------------------------------------------------------------
# Fallback (no Accept: application/json) — old plain-HTML behavior intact
# ---------------------------------------------------------------------------


def test_post_tarefas_without_json_headers_still_redirects_303(
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
    assert "application/json" not in response.headers.get("content-type", "")


def test_post_tarefas_concluir_without_json_headers_still_redirects_303(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        tarefa = create_tarefa(titulo="Tarefa concluída sem AJAX")

        response = client.post(
            f"/tarefas/{tarefa['id']}/concluir", follow_redirects=False
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_post_tarefas_remover_without_json_headers_still_redirects_303(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        tarefa = create_tarefa(titulo="Tarefa removida sem AJAX")

        response = client.post(
            f"/tarefas/{tarefa['id']}/remover", follow_redirects=False
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


# ---------------------------------------------------------------------------
# GET /tarefas/fragmento
# ---------------------------------------------------------------------------


def test_get_tarefas_fragmento_returns_200(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/tarefas/fragmento")

    assert response.status_code == 200


def test_get_tarefas_fragmento_contains_task_and_not_the_panel_shell(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        create_tarefa(titulo="Publicar reels da semana")

        response = client.get("/tarefas/fragmento")

    assert response.status_code == 200
    assert "Publicar reels da semana" in response.text
    assert "tarefa-card" in response.text
    assert "<nav" not in response.text
    assert "topbar" not in response.text


def test_get_tarefas_fragmento_shows_empty_state_when_no_open_tasks(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/tarefas/fragmento")

    assert response.status_code == 200
    assert "Nenhuma tarefa" in response.text
    assert "tarefas-vazio" in response.text


# ---------------------------------------------------------------------------
# GET / (Início) — modal markup
# ---------------------------------------------------------------------------


def test_inicio_contains_tarefas_modal_markup(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    text = response.text
    assert "v-modal-tarefas" in text
    assert 'id="tarefas-modal"' in text
    assert 'id="tarefas-toggle"' in text
    assert 'id="tarefa-add-form"' in text
    assert 'id="tarefas-lista-container"' in text
