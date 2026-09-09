"""Tests for issue 03 (sub-aba Agenda com a lista real).

Covers the functional specification:
- with no scheduled sessions, GET /alunos/{id}/agenda shows the empty-state
  message and the "Agendar sessão" button (linking to
  /alunos/{id}/agenda/nova);
- the Agenda sub-tab is the active one (its <a> carries class "on") and does
  not carry the "em breve" marker (unlike Feedback/Financeiro);
- with several sessions created out of order, the list shows them in
  chronological order (oldest first), each with its date (DD/MM/AAAA), hour
  (HH:MM) and type ("Individual"/"Grupo");
- a NULL duracao_min is shown as "sem registro" in the list;
- an unknown aluno id -> 404 in the brand's visual.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.agenda.service import create_sessao
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


def test_no_sessions_shows_empty_state_and_schedule_button(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/agenda")

    assert response.status_code == 200
    assert "Ainda não há sessões" in response.text
    assert (
        f'<a class="button-link" href="/alunos/{aluno["id"]}/agenda/nova">'
        "Agendar sessão</a>" in response.text
    )


def test_agenda_subtab_is_active_and_has_no_coming_soon_marker(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/agenda")

    assert response.status_code == 200

    active_link = f'<a class="on" href="/alunos/{aluno["id"]}/agenda">Agenda</a>'
    assert active_link in response.text, (
        "the Agenda link should be active and free of the em-breve span"
        " (its full <a> tag has no trailing content beyond the label)"
    )

    # Scope the "em breve" check to the Agenda tab's own <a> tag: the
    # sub-nav's Feedback/Financeiro tabs (and the base template's unrelated
    # top-level nav) legitimately still carry "em breve" markers elsewhere
    # on the page.
    nav_match = re.search(r"<nav[^>]*subnav[^>]*>(.*?)</nav>", response.text, re.DOTALL)
    assert nav_match is not None, "the ficha page should have a subnav"
    nav_html = nav_match.group(1)

    tab_link = re.search(
        rf'<a[^>]*href="/alunos/{aluno["id"]}/agenda"[^>]*>(.*?)</a>',
        nav_html,
        re.DOTALL,
    )
    assert tab_link is not None
    assert "em breve" not in tab_link.group(1)


def test_list_shows_sessions_in_chronological_order_with_data_hora_tipo(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        # Created out of chronological order on purpose.
        newest = create_sessao(
            aluno["id"], data="2026-03-01", hora="09:00", tipo="individual"
        )
        oldest = create_sessao(
            aluno["id"], data="2026-01-10", hora="18:30", tipo="grupo"
        )
        middle = create_sessao(
            aluno["id"], data="2026-02-15", hora="07:00", tipo="individual"
        )

        response = client.get(f"/alunos/{aluno['id']}/agenda")

    assert response.status_code == 200
    text = response.text

    oldest_pos = text.index("10/01/2026")
    middle_pos = text.index("15/02/2026")
    newest_pos = text.index("01/03/2026")

    assert oldest_pos < middle_pos < newest_pos, (
        "the oldest session should appear before the others in the HTML"
    )

    assert "18:30" in text
    assert "07:00" in text
    assert "09:00" in text
    assert "Individual" in text
    assert "Grupo" in text


def test_null_duracao_is_shown_as_sem_registro(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_sessao(aluno["id"], data="2026-01-15", hora="08:00", tipo="individual")

        response = client.get(f"/alunos/{aluno['id']}/agenda")

    assert response.status_code == 200
    assert "sem registro" in response.text


def test_unknown_aluno_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999/agenda")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text
