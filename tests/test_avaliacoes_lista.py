"""Tests for issue 03 (sub-aba Avaliações com a lista real).

Covers the functional specification:
- with no assessments, GET /alunos/{id}/avaliacoes shows the empty-state
  message and the "Registar avaliação" button (linking to
  /alunos/{id}/avaliacoes/nova);
- the Avaliações sub-tab is the active one (its <a> carries class "on") and
  does not carry the "em breve" marker (unlike Feedback/Agenda/Financeiro);
- with several assessments on different dates, the list shows them in
  reverse chronological order (most recent first), each linking to
  /alunos/{id}/avaliacoes/{avaliacao_id};
- a NULL metric (e.g. an assessment with only date and weight) is shown as
  "sem registro" in the list;
- an unknown aluno id -> 404 in the brand's visual.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.avaliacoes.service import create_avaliacao
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_no_assessments_shows_empty_state_and_register_button(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    assert "Ainda não há avaliações" in response.text
    assert (
        f'<a class="button-link" href="/alunos/{aluno["id"]}/avaliacoes/nova">'
        "Registar avaliação</a>" in response.text
    )


def test_avaliacoes_subtab_is_active_and_has_no_coming_soon_marker(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200

    active_link = f'<a class="on" href="/alunos/{aluno["id"]}/avaliacoes">Avaliações</a>'
    assert active_link in response.text, (
        "the Avaliações link should be active and free of the em-breve span"
        " (its full <a> tag has no trailing content beyond the label)"
    )


def test_list_shows_assessments_in_reverse_chronological_order_with_links(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        oldest = create_avaliacao(aluno["id"], data="2026-01-10", peso="70")
        newest = create_avaliacao(aluno["id"], data="2026-03-01", peso="71")
        middle = create_avaliacao(aluno["id"], data="2026-02-15", peso="72")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    for avaliacao in (newest, middle, oldest):
        assert (
            f'href="/alunos/{aluno["id"]}/avaliacoes/{avaliacao["id"]}"' in text
        ), f"assessment {avaliacao['id']} should link to its detail page"

    newest_pos = text.index(f'/avaliacoes/{newest["id"]}"')
    middle_pos = text.index(f'/avaliacoes/{middle["id"]}"')
    oldest_pos = text.index(f'/avaliacoes/{oldest["id"]}"')

    assert newest_pos < middle_pos < oldest_pos, (
        "the most recent assessment should appear before the others in the HTML"
    )

    assert "01/03/2026" in text
    assert "15/02/2026" in text
    assert "10/01/2026" in text


def test_null_metric_is_shown_as_sem_registro(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-15", peso="70")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    assert "sem registro" in response.text


def test_unknown_aluno_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999/avaliacoes")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text
