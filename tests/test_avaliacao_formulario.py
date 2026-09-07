"""Tests for issue 04 (formulário de nova avaliação).

Covers the functional specification:
- GET /alunos/{id}/avaliacoes/nova shows the new-assessment form (date,
  peso, altura, % gordura, massa magra, massa gorda fields);
- POST /alunos/{id}/avaliacoes with valid data creates the assessment and
  redirects (303) to /alunos/{id}/avaliacoes, where it now appears;
- missing date, negative number or non-numeric number -> 400, re-renders the
  form with the service's error message and nothing is persisted;
- an empty numeric field is stored as NULL;
- typed values are preserved in the re-rendered form on error;
- an unknown aluno id -> 404 for both GET and POST.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.avaliacoes.service import list_avaliacoes
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_new_form_returns_200_with_all_fields(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/nova")

    assert response.status_code == 200
    text = response.text
    assert 'name="data"' in text
    assert 'name="peso"' in text
    assert 'name="altura"' in text
    assert 'name="gordura_pct"' in text
    assert 'name="massa_magra"' in text
    assert 'name="massa_gorda"' in text
    assert f'action="/alunos/{aluno["id"]}/avaliacoes"' in text


def test_valid_post_redirects_and_new_assessment_appears_in_list(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={"data": "2026-03-01", "peso": "72.5"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/alunos/{aluno['id']}/avaliacoes"

        followed = client.get(response.headers["location"])

    assert followed.status_code == 200
    assert "01/03/2026" in followed.text
    assert "72.5" in followed.text


def test_post_without_date_returns_400_and_persists_nothing(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={"peso": "70"},
        )

        avaliacoes = list_avaliacoes(aluno["id"])

    assert response.status_code == 400
    assert "Data é obrigatória." in response.text
    assert avaliacoes == []


def test_post_with_negative_peso_returns_400_and_persists_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={"data": "2026-03-01", "peso": "-5"},
        )

        avaliacoes = list_avaliacoes(aluno["id"])

    assert response.status_code == 400
    assert "não pode ser negativo" in response.text
    assert avaliacoes == []


def test_post_with_non_numeric_peso_returns_400_and_persists_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={"data": "2026-03-01", "peso": "abc"},
        )

        avaliacoes = list_avaliacoes(aluno["id"])

    assert response.status_code == 400
    assert "Peso inválido." in response.text
    assert avaliacoes == []


def test_empty_numeric_fields_are_stored_as_null(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={
                "data": "2026-03-01",
                "peso": "72.5",
                "altura": "",
                "gordura_pct": "",
                "massa_magra": "",
                "massa_gorda": "",
            },
            follow_redirects=False,
        )

        avaliacoes = list_avaliacoes(aluno["id"])

    assert response.status_code == 303
    assert len(avaliacoes) == 1
    created = avaliacoes[0]
    assert created["altura"] is None
    assert created["gordura_pct"] is None
    assert created["massa_magra"] is None
    assert created["massa_gorda"] is None


def test_invalid_post_preserves_typed_values_in_the_form(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={"peso": "80"},
        )

    assert response.status_code == 400
    assert 'name="peso" value="80"' in response.text


def test_unknown_aluno_id_returns_404_for_get_and_post(data_dir: Path) -> None:
    with TestClient(app) as client:
        get_response = client.get("/alunos/999/avaliacoes/nova")
        post_response = client.post(
            "/alunos/999/avaliacoes",
            data={"data": "2026-03-01", "peso": "70"},
        )

    assert get_response.status_code == 404
    assert "Aluno não encontrado." in get_response.text

    assert post_response.status_code == 404
    assert "Aluno não encontrado." in post_response.text
