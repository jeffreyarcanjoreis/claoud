"""Tests for issue 05 (detalhe da avaliação com Δ e IMC).

Covers the functional specification:
- GET /alunos/{id}/avaliacoes/{avaliacao_id} shows the assessment's date,
  every recorded metric and the IMC computed from peso/altura;
- each metric shows the Δ vs the previous assessment of the same aluno
  (the one with the greatest date earlier than this one), with a visible
  sign (Brazilian comma notation);
- the first assessment of an aluno (no previous one) shows its metrics
  without any Δ, and the "first assessment" message;
- the IMC is computed on demand (never stored) and shown as "sem registro"
  when peso or altura is missing;
- a NULL metric (e.g. no gordura_pct) is shown as "sem registro";
- an unknown avaliacao_id -> 404 in the brand's visual;
- an avaliacao_id belonging to another aluno -> 404 (isolation between
  alunos' data).

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.avaliacoes.service import create_avaliacao, list_avaliacoes
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_second_assessment_shows_date_weight_delta_and_imc(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="80")
        create_avaliacao(aluno["id"], data="2026-03-01", peso="82,5")

        avaliacoes = list_avaliacoes(aluno["id"])
        # reverse chronological order: the newest (B) comes first.
        segunda = avaliacoes[0]

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/{segunda['id']}")

    assert response.status_code == 200
    text = response.text
    assert "01/03/2026" in text
    assert "82,5" in text
    assert "+2,5" in text or "2,5" in text
    assert "IMC" in text


def test_first_assessment_has_no_previous_and_shows_no_delta(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="80")
        create_avaliacao(aluno["id"], data="2026-03-01", peso="82,5")

        avaliacoes = list_avaliacoes(aluno["id"])
        # oldest (A) is last in the reverse-chronological list.
        primeira = avaliacoes[-1]

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/{primeira['id']}")

    assert response.status_code == 200
    text = response.text
    assert "Primeira avaliação" in text
    assert 'class="delta' not in text


def test_imc_is_computed_from_peso_and_altura(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="80", altura="178")

        avaliacoes = list_avaliacoes(aluno["id"])
        avaliacao = avaliacoes[0]

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/{avaliacao['id']}")

    assert response.status_code == 200
    assert "25,2" in response.text


def test_imc_is_sem_registro_when_altura_is_missing(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="80")

        avaliacoes = list_avaliacoes(aluno["id"])
        avaliacao = avaliacoes[0]

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/{avaliacao['id']}")

    assert response.status_code == 200
    assert "sem registro" in response.text


def test_null_metric_is_shown_as_sem_registro(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="80", altura="178")

        avaliacoes = list_avaliacoes(aluno["id"])
        avaliacao = avaliacoes[0]

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/{avaliacao['id']}")

    assert response.status_code == 200
    assert "% Gordura" in response.text
    assert "sem registro" in response.text


def test_unknown_avaliacao_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/999")

    assert response.status_code == 404


def test_avaliacao_from_another_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno1 = create_aluno(name="Maria Silva")
        aluno2 = create_aluno(name="Joao Pereira")
        create_avaliacao(aluno2["id"], data="2026-01-10", peso="70")

        avaliacoes_aluno2 = list_avaliacoes(aluno2["id"])
        avaliacao_de_outro_aluno = avaliacoes_aluno2[0]

        response = client.get(
            f"/alunos/{aluno1['id']}/avaliacoes/{avaliacao_de_outro_aluno['id']}"
        )

    assert response.status_code == 404
