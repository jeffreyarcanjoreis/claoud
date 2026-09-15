"""Tests for issue 09: student list status filter (filtro da lista por status).

Covers the functional specification:
- GET /alunos?status=active shows only active students;
- GET /alunos?status=inactive shows only inactive students;
- GET /alunos (no query param) shows both;
- an unknown status value in the query param is ignored defensively (shows
  all students, 200, never a 500);
- the "Todos | Ativos | Inativos" filter bar is present on the list page.

Same isolation pattern as tests/test_lista_alunos.py: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def _create_active_and_inactive(client: TestClient) -> None:
    """Create one active and one inactive student via cadastro + edição."""
    client.post("/alunos", data={"name": "Ana Ativa"}, follow_redirects=False)
    client.post("/alunos", data={"name": "Bruno Inativo"}, follow_redirects=False)
    # Ana Ativa is student id 1, Bruno Inativo is id 2 (created in this order).
    client.post(
        "/alunos/2",
        data={"name": "Bruno Inativo", "status": "inactive"},
        follow_redirects=False,
    )


def test_filter_active_shows_only_active_student(data_dir: Path) -> None:
    with TestClient(app) as client:
        _create_active_and_inactive(client)
        response = client.get("/alunos?status=active")

    assert response.status_code == 200
    assert "Ana Ativa" in response.text
    assert "Bruno Inativo" not in response.text


def test_filter_inactive_shows_only_inactive_student(data_dir: Path) -> None:
    with TestClient(app) as client:
        _create_active_and_inactive(client)
        response = client.get("/alunos?status=inactive")

    assert response.status_code == 200
    assert "Bruno Inativo" in response.text
    assert "Ana Ativa" not in response.text


def test_no_filter_shows_both_students(data_dir: Path) -> None:
    with TestClient(app) as client:
        _create_active_and_inactive(client)
        response = client.get("/alunos")

    assert response.status_code == 200
    assert "Ana Ativa" in response.text
    assert "Bruno Inativo" in response.text


def test_unknown_status_value_shows_all_students_without_error(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        _create_active_and_inactive(client)
        response = client.get("/alunos?status=xpto")

    assert response.status_code == 200
    assert "Ana Ativa" in response.text
    assert "Bruno Inativo" in response.text


def test_filter_bar_links_are_present(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200
    assert "Todos" in response.text
    assert "Ativos" in response.text
    assert "Inativos" in response.text
    assert 'href="/alunos?status=active"' in response.text
    assert 'href="/alunos?status=inactive"' in response.text
