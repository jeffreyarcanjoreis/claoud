"""Tests for issue 24: the "alunos" (students) archive / reactivate / delete
routes (``POST /alunos/{id}/arquivar``, ``POST /alunos/{id}/reativar``,
``GET`` and ``POST /alunos/{id}/excluir``).

Covers the functional specification:
- POST /alunos/{id}/arquivar sets status to inactive and redirects (303) to
  /alunos/{id}; 404 for a non-existent id;
- POST /alunos/{id}/reativar sets status back to active and redirects (303)
  to /alunos/{id}; 404 for a non-existent id;
- GET /alunos/{id}/excluir renders a confirmation page (200); when the
  student has no history, it shows the POST .../excluir delete form; when it
  has history, that form is absent (only the archive form/link remain); 404
  for a non-existent id;
- POST /alunos/{id}/excluir deletes the student and redirects (303) to
  /alunos when there is no history, and the student disappears from the
  list; refuses (nothing deleted, student still reachable) when there is
  history; 404 for a non-existent id.

Same isolation pattern as the other route suites: KAIROS_DATA_DIR points at
a temp dir and the cached engine is disposed on setup/teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno, get_aluno
from kairos.financeiro.service import registrar_pagamento
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# POST /alunos/{id}/arquivar
# ---------------------------------------------------------------------------


def test_arquivar_route_sets_status_inactive_and_redirects(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")

        response = client.post(
            f"/alunos/{aluno['id']}/arquivar", follow_redirects=False
        )

        loaded = get_aluno(aluno["id"])

    assert response.status_code == 303
    assert response.headers["location"] == f"/alunos/{aluno['id']}"
    assert loaded is not None
    assert loaded["status"] == "inactive"


def test_arquivar_route_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/alunos/9999/arquivar", follow_redirects=False)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /alunos/{id}/reativar
# ---------------------------------------------------------------------------


def test_reativar_route_sets_status_active_and_redirects(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        client.post(f"/alunos/{aluno['id']}/arquivar", follow_redirects=False)

        response = client.post(
            f"/alunos/{aluno['id']}/reativar", follow_redirects=False
        )

        loaded = get_aluno(aluno["id"])

    assert response.status_code == 303
    assert response.headers["location"] == f"/alunos/{aluno['id']}"
    assert loaded is not None
    assert loaded["status"] == "active"


def test_reativar_route_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/alunos/9999/reativar", follow_redirects=False)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /alunos/{id}/excluir (confirmation page)
# ---------------------------------------------------------------------------


def test_excluir_confirma_shows_confirmation_page(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")

        response = client.get(f"/alunos/{aluno['id']}/excluir")

    assert response.status_code == 200
    assert "Maria Silva" in response.text


def test_excluir_confirma_without_history_shows_delete_form(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")

        response = client.get(f"/alunos/{aluno['id']}/excluir")

    assert response.status_code == 200
    assert f'action="/alunos/{aluno["id"]}/excluir"' in response.text


def test_excluir_confirma_with_history_hides_delete_form(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        registrar_pagamento(aluno["id"], ano=2026, mes=1, valor="100")

        response = client.get(f"/alunos/{aluno['id']}/excluir")

    assert response.status_code == 200
    assert f'action="/alunos/{aluno["id"]}/excluir"' not in response.text
    assert f'action="/alunos/{aluno["id"]}/arquivar"' in response.text


def test_excluir_confirma_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/9999/excluir")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /alunos/{id}/excluir (perform delete)
# ---------------------------------------------------------------------------


def test_excluir_route_without_history_deletes_and_redirects(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")

        response = client.post(
            f"/alunos/{aluno['id']}/excluir", follow_redirects=False
        )

        loaded = get_aluno(aluno["id"])
        listagem = client.get("/alunos")

    assert response.status_code == 303
    assert response.headers["location"] == "/alunos"
    assert loaded is None
    assert "Maria Silva" not in listagem.text


def test_excluir_route_with_history_refuses_and_keeps_aluno(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        registrar_pagamento(aluno["id"], ano=2026, mes=1, valor="100")

        response = client.post(
            f"/alunos/{aluno['id']}/excluir", follow_redirects=False
        )

        loaded = get_aluno(aluno["id"])

    assert response.status_code == 200
    assert loaded is not None
    assert loaded["id"] == aluno["id"]


def test_excluir_route_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/alunos/9999/excluir", follow_redirects=False)

    assert response.status_code == 404
