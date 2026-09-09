"""Tests for issue 04 (perimetria no detalhe da avaliação com Δ).

Covers the functional specification:
- the assessment detail page shows a "Perimetria (cm)" section listing each
  segment measured in that assessment, with its value and the Δ vs the same
  segment in the aluno's previous assessment (computed on demand, never
  stored);
- the first assessment of an aluno (no previous one) shows its perimetria
  without any Δ;
- a segment measured only in the current assessment (absent from the
  previous one) shows its value without a Δ, while a segment present in
  both shows a Δ;
- an assessment with no perimetria at all shows "sem registro" in that
  section (nothing invented);
- an unknown avaliacao_id -> 404 (regression).

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

import re
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


def _row_for(text: str, label: str) -> str:
    """Return the HTML snippet of the perimetria row for a given segment label."""
    match = re.search(
        r'<div class="row">\s*<dt class="k">' + re.escape(label) + r"</dt>.*?</div>",
        text,
        re.DOTALL,
    )
    assert match is not None, f"row for {label!r} not found in:\n{text}"
    return match.group(0)


def test_second_assessment_shows_perimetria_value_and_delta(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", perimetria={"cintura": "84"})
        create_avaliacao(aluno["id"], data="2026-03-01", perimetria={"cintura": "82"})

        avaliacoes = list_avaliacoes(aluno["id"])
        # reverse chronological order: the newest (2026-03-01) comes first.
        segunda = avaliacoes[0]

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/{segunda['id']}")

    assert response.status_code == 200
    text = response.text
    assert "Perimetria" in text
    assert "Cintura" in text
    assert "82" in text
    assert 'class="delta delta-down"' in text
    assert "−2" in text or "-2" in text


def test_first_assessment_shows_perimetria_without_delta(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", perimetria={"cintura": "84"})
        create_avaliacao(aluno["id"], data="2026-03-01", perimetria={"cintura": "82"})

        avaliacoes = list_avaliacoes(aluno["id"])
        # oldest is last in the reverse-chronological list; no previous one.
        primeira = avaliacoes[-1]

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/{primeira['id']}")

    assert response.status_code == 200
    text = response.text
    assert "Cintura" in text
    assert "84" in text
    assert 'class="delta' not in text


def test_segment_measured_only_in_current_assessment_has_no_delta(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", perimetria={"cintura": "90"})
        create_avaliacao(
            aluno["id"],
            data="2026-03-01",
            perimetria={"cintura": "88", "coxa_d": "50"},
        )

        avaliacoes = list_avaliacoes(aluno["id"])
        segunda = avaliacoes[0]

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/{segunda['id']}")

    assert response.status_code == 200
    text = response.text

    coxa_row = _row_for(text, "Coxa D")
    assert "delta" not in coxa_row

    cintura_row = _row_for(text, "Cintura")
    assert "delta" in cintura_row


def test_assessment_without_perimetria_shows_sem_registro(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="80")

        avaliacoes = list_avaliacoes(aluno["id"])
        avaliacao = avaliacoes[0]

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/{avaliacao['id']}")

    assert response.status_code == 200
    text = response.text
    assert "Perimetria (cm)" in text
    assert '<p><span class="none">sem registro</span></p>' in text


def test_unknown_avaliacao_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/999")

    assert response.status_code == 404
