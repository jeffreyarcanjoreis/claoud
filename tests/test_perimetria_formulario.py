"""Tests for issue 03 (secção de perimetria no formulário de nova avaliação).

Covers the functional specification:
- GET /alunos/{id}/avaliacoes/nova shows the "Perimetria (cm)" section with a
  field per segment of PERIMETRIA_SEGMENTOS (name "perim_<key>"), each
  labeled with its display name;
- POST /alunos/{id}/avaliacoes collects the perimetria fields and passes them
  to the service; filled segments are saved as rows;
- a negative perimetria value -> 400, nothing persisted (neither the
  avaliacao nor any perimetria row), and the typed value is preserved in the
  re-rendered form;
- POST with no perimetria field filled -> the avaliacao is created with 0
  measurements;
- the antropometric fields still work on their own (regression).

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.avaliacoes.service import list_avaliacoes, list_perimetria
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_new_form_shows_perimetria_section_and_segment_fields(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/avaliacoes/nova")

    assert response.status_code == 200
    text = response.text
    assert "<h3>Perimetria (cm)</h3>" in text
    assert 'name="perim_cintura"' in text
    assert 'name="perim_coxa_d"' in text
    assert 'name="perim_pescoco"' in text
    assert "Cintura" in text


def test_valid_post_with_perimetria_saves_measurements(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={
                "data": "2026-03-01",
                "perim_cintura": "82,5",
                "perim_coxa_d": "58",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/alunos/{aluno['id']}/avaliacoes"

        avaliacoes = list_avaliacoes(aluno["id"])
        assert len(avaliacoes) == 1
        medidas = list_perimetria(avaliacoes[0]["id"])

    assert len(medidas) == 2
    by_segmento = {m["segmento"]: m["valor"] for m in medidas}
    assert set(by_segmento) == {"Cintura", "Coxa D"}
    assert by_segmento["Cintura"] == pytest.approx(82.5)
    assert by_segmento["Coxa D"] == pytest.approx(58)


def test_post_with_negative_perimetria_returns_400_and_persists_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={"data": "2026-03-01", "perim_cintura": "-5"},
        )

        avaliacoes = list_avaliacoes(aluno["id"])

    assert response.status_code == 400
    assert "não pode ser negativo" in response.text
    assert avaliacoes == []
    assert 'name="perim_cintura"' in response.text
    assert 'value="-5"' in response.text


def test_post_without_any_perimetria_creates_assessment_with_no_measurements(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={"data": "2026-03-01"},
            follow_redirects=False,
        )

        assert response.status_code == 303

        avaliacoes = list_avaliacoes(aluno["id"])
        assert len(avaliacoes) == 1
        medidas = list_perimetria(avaliacoes[0]["id"])

    assert medidas == []


def test_post_with_only_antropometric_fields_still_works(data_dir: Path) -> None:
    """Regression: antropometric fields still work without any perimetria."""
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/avaliacoes",
            data={"data": "2026-03-01", "peso": "72.5"},
            follow_redirects=False,
        )

        assert response.status_code == 303

        avaliacoes = list_avaliacoes(aluno["id"])

    assert len(avaliacoes) == 1
    assert avaliacoes[0]["peso"] == pytest.approx(72.5)
