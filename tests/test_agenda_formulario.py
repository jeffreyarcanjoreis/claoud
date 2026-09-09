"""Tests for issue 04 (formulário de agendar sessão).

Covers the functional specification:
- GET /alunos/{id}/agenda/nova shows the new-session form (data, hora,
  duração opcional, tipo, observação opcional);
- POST /alunos/{id}/agenda with valid data creates the session and
  redirects (303) to /alunos/{id}/agenda, where it appears in the list;
- missing data, missing hora, invalid tipo, or non-positive duracao_min ->
  400, re-render of the form with the error message and the submitted
  values preserved; nothing is persisted;
- empty optional fields (duracao_min, observacao) become NULL;
- an unknown aluno id -> 404, on both GET and POST.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.agenda.service import list_sessoes
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


def test_get_new_session_form_shows_all_fields(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/agenda/nova")

    assert response.status_code == 200
    assert 'name="data"' in response.text
    assert 'name="hora"' in response.text
    assert 'name="tipo"' in response.text
    assert 'name="duracao_min"' in response.text
    assert 'name="observacao"' in response.text


def test_post_valid_creates_session_and_redirects_to_list(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/agenda",
            data={
                "data": "2026-09-01",
                "hora": "09:00",
                "tipo": "individual",
                "duracao_min": "60",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/alunos/{aluno['id']}/agenda"

        followed = client.get(response.headers["location"])
        assert followed.status_code == 200
        assert "01/09/2026" in followed.text
        assert "09:00" in followed.text
        assert "Individual" in followed.text

        sessoes = list_sessoes(aluno["id"])

    assert len(sessoes) == 1
    assert sessoes[0]["data"].isoformat() == "2026-09-01"
    assert sessoes[0]["hora"].strftime("%H:%M") == "09:00"
    assert sessoes[0]["tipo"] == "individual"
    assert sessoes[0]["duracao_min"] == 60


def test_post_without_data_returns_400_and_persists_nothing(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/agenda",
            data={"hora": "09:00", "tipo": "individual"},
        )

        assert response.status_code == 400
        assert "Data é obrigatória." in response.text
        assert list_sessoes(aluno["id"]) == []


def test_post_without_hora_returns_400_and_persists_nothing(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/agenda",
            data={"data": "2026-09-01", "tipo": "individual"},
        )

        assert response.status_code == 400
        assert "Hora é obrigatória." in response.text
        assert list_sessoes(aluno["id"]) == []


def test_post_invalid_tipo_returns_400_and_persists_nothing(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/agenda",
            data={"data": "2026-09-01", "hora": "09:00", "tipo": "x"},
        )

        assert response.status_code == 400
        assert "Tipo inválido." in response.text
        assert list_sessoes(aluno["id"]) == []


@pytest.mark.parametrize("duracao_min", ["0", "-5"])
def test_post_non_positive_duracao_returns_400_and_persists_nothing(
    data_dir: Path, duracao_min: str
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/agenda",
            data={
                "data": "2026-09-01",
                "hora": "09:00",
                "tipo": "individual",
                "duracao_min": duracao_min,
            },
        )

        assert response.status_code == 400
        assert "Duração deve ser positiva." in response.text
        assert list_sessoes(aluno["id"]) == []


def test_post_empty_optional_fields_become_null(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/agenda",
            data={
                "data": "2026-09-01",
                "hora": "09:00",
                "tipo": "individual",
                "duracao_min": "",
                "observacao": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        sessoes = list_sessoes(aluno["id"])

    assert len(sessoes) == 1
    assert sessoes[0]["duracao_min"] is None
    assert sessoes[0]["observacao"] is None


def test_post_invalid_preserves_submitted_values(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/agenda",
            data={"hora": "09:00", "tipo": "grupo"},
        )

    assert response.status_code == 400
    assert (
        'value="09:00"' in response.text
    ), "the submitted hora should be preserved in the re-rendered form"
    assert (
        '<option value="grupo" selected>Grupo</option>' in response.text
    ), "the submitted tipo (grupo) should stay selected in the re-rendered form"


def test_get_new_session_form_unknown_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999/agenda/nova")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_post_unknown_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos/999/agenda",
            data={"data": "2026-09-01", "hora": "09:00", "tipo": "individual"},
        )

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text
