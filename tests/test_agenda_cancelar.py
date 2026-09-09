"""Tests for issue 05 (cancelar uma sessão).

Covers the functional specification:
- each session in the list is rendered with a POST form/button pointing at
  the cancel route (a cancel action must never be a plain GET link);
- POST /alunos/{aluno_id}/agenda/{sessao_id}/cancelar removes the session
  and redirects (303) to /alunos/{aluno_id}/agenda; the session no longer
  appears in list_sessoes;
- POST of an unknown sessao_id -> 404;
- POST of a session that belongs to ANOTHER student, via this student's
  URL, -> 404 (isolation: a session can never be cancelled through another
  student's URL);
- unknown aluno id -> 404.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.agenda.service import create_sessao, list_sessoes
from kairos.alunos.service import create_aluno
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_list_shows_cancel_form_pointing_at_cancel_route(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        sessao = create_sessao(
            aluno["id"], data="2026-01-15", hora="08:00", tipo="individual"
        )

        response = client.get(f"/alunos/{aluno['id']}/agenda")

    assert response.status_code == 200
    action = f'/alunos/{aluno["id"]}/agenda/{sessao["id"]}/cancelar'
    assert f'<form method="post" action="{action}"' in response.text
    assert 'class="btn-cancelar"' in response.text


def test_cancel_removes_session_and_redirects(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        sessao = create_sessao(
            aluno["id"], data="2026-01-15", hora="08:00", tipo="individual"
        )

        response = client.post(
            f"/alunos/{aluno['id']}/agenda/{sessao['id']}/cancelar",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/alunos/{aluno['id']}/agenda"
        assert list_sessoes(aluno["id"]) == []


def test_cancel_unknown_sessao_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")

        response = client.post(f"/alunos/{aluno['id']}/agenda/999/cancelar")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_cancel_session_of_another_student_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno1 = create_aluno(name="Maria Silva")
        aluno2 = create_aluno(name="João Souza")
        sessao_de_aluno2 = create_sessao(
            aluno2["id"], data="2026-01-15", hora="08:00", tipo="individual"
        )

        response = client.post(
            f"/alunos/{aluno1['id']}/agenda/{sessao_de_aluno2['id']}/cancelar"
        )

        assert response.status_code == 404
        assert "Aluno não encontrado." in response.text
        # The other student's session must survive untouched.
        assert len(list_sessoes(aluno2["id"])) == 1


def test_cancel_unknown_aluno_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/alunos/999/agenda/1/cancelar")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text
