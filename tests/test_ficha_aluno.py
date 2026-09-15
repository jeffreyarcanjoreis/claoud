"""Tests for issue 04 (ficha do aluno com sub-abas).

Covers the functional specification:
- GET /alunos/{id} renders the "ficha" with a sub-nav containing the six
  sub-tabs (Perfil, Avaliações, Treino, Acompanhamento, Agenda, Financeiro)
  and Perfil is the active one by default (class "on" on its
  <a href="/alunos/{id}">);
- the profile content (labels, values) is still present on that same page;
- each sub-tab route (/avaliacoes, /financeiro) answers 200, shows the
  student's name and the sub-tab of the moment active (/avaliacoes,
  /treino, /acompanhamento, /agenda and, as of issue 15, /financeiro all
  have real content instead of a placeholder — see test_avaliacoes_lista.py,
  test_treinos_planilha.py, test_acompanhamento.py, test_agenda_lista.py
  and test_financeiro.py);
- none of Perfil, Avaliações, Treino, Acompanhamento, Agenda or Financeiro
  carry a "coming soon" marker in the sub-nav anymore (issue 13 renamed the
  "Feedback" sub-tab to "Acompanhamento" and gave it real content, so it is
  no longer a placeholder and no longer linked as "Feedback" in the
  sub-nav; issue 15 did the same for Financeiro);
- the old /alunos/{id}/feedback route still answers 200 with a "coming
  soon" body (issue 13: it is now an orphan route, simply unlinked from the
  sub-nav — cleanup left for later, its behavior is otherwise unchanged);
- an unknown id on any sub-tab route -> 404 in the brand's visual (same as
  the profile route);
- regression: /alunos/{id}/editar and /alunos/novo keep answering 200 (the
  new routes did not swallow the existing ones).

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a
temp dir and the cached engine is disposed on teardown.
"""

import re
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


def _create_aluno(client: TestClient, data: dict) -> str:
    """POST a student and return its profile URL (via the list page link)."""
    client.post("/alunos", data=data, follow_redirects=False)
    lista = client.get("/alunos")
    match = re.search(r'href="(/alunos/\d+)"', lista.text)
    assert match is not None, "list card should link to the profile"
    return match.group(1)


# Avaliações, Treino, Acompanhamento, Agenda and (as of issue 15) Financeiro
# are no longer placeholders: they now list the student's real assessments/
# workouts/held sessions/scheduled sessions/plan (or an empty-state
# message), so no sub-tab carries the "em breve" marker in the sub-nav
# anymore. Only the orphan (unlinked) /feedback route still shows a "coming
# soon" body -- see test_orphan_feedback_route_still_returns_200_with_coming_soon_body.


def _has_coming_soon(text: str) -> bool:
    """True when the "coming soon" body marker is present in the page."""
    return "coming-soon" in text or "em breve" in text or "por construir" in text


def test_profile_page_has_subnav_with_six_tabs_and_perfil_active(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        profile_url = _create_aluno(client, {"name": "Maria Silva"})
        response = client.get(profile_url)

    assert response.status_code == 200
    for label in [
        "Perfil",
        "Avaliações",
        "Treino",
        "Acompanhamento",
        "Agenda",
        "Financeiro",
    ]:
        assert label in response.text

    aluno_id = profile_url.rsplit("/", 1)[-1]
    perfil_link = re.search(
        rf'<a class="([^"]*)" href="/alunos/{aluno_id}">Perfil</a>', response.text
    )
    assert perfil_link is not None, "Perfil link should exist as an <a> tag"
    assert "on" in perfil_link.group(1).split()


def test_profile_page_shows_profile_content(data_dir: Path) -> None:
    with TestClient(app) as client:
        profile_url = _create_aluno(
            client, {"name": "Maria Silva", "objective": "Hipertrofia geral"}
        )
        response = client.get(profile_url)

    assert response.status_code == 200
    assert "Maria Silva" in response.text
    assert "Objetivo" in response.text
    assert "Hipertrofia geral" in response.text


def test_orphan_feedback_route_still_returns_200_with_coming_soon_body(
    data_dir: Path,
) -> None:
    """Issue 13 renamed the "Feedback" sub-tab to "Acompanhamento" and gave
    it real content, unlinking the old /feedback route from the sub-nav.
    The route itself is left untouched (cleanup for later): it still
    answers 200 with the student's name and a "coming soon" body, it just
    no longer has an active link anywhere in the sub-nav."""
    with TestClient(app) as client:
        profile_url = _create_aluno(client, {"name": "Maria Silva"})
        response = client.get(f"{profile_url}/feedback")

    assert response.status_code == 200
    assert "Maria Silva" in response.text
    assert _has_coming_soon(response.text)

    nav_match = re.search(r"<nav[^>]*subnav[^>]*>(.*?)</nav>", response.text, re.DOTALL)
    assert nav_match is not None
    aluno_id = profile_url.rsplit("/", 1)[-1]
    assert f'href="/alunos/{aluno_id}/feedback"' not in nav_match.group(1)


def test_avaliacoes_subtab_route_returns_200_with_name_and_active_tab(
    data_dir: Path,
) -> None:
    """Avaliações is a real sub-tab now, not a placeholder: the route must
    still return 200 with the student's name and mark the tab active, but it
    no longer has to show a "coming soon" body (see test_avaliacoes_lista.py
    for the actual list/empty-state coverage)."""
    with TestClient(app) as client:
        profile_url = _create_aluno(client, {"name": "Maria Silva"})
        response = client.get(f"{profile_url}/avaliacoes")

    assert response.status_code == 200
    assert "Maria Silva" in response.text

    aluno_id = profile_url.rsplit("/", 1)[-1]
    active_link = re.search(
        rf'<a class="([^"]*)" href="/alunos/{aluno_id}/avaliacoes">', response.text
    )
    assert active_link is not None, "avaliacoes link should exist as an <a> tag"
    assert "on" in active_link.group(1).split()


def test_financeiro_subtab_route_returns_200_with_name_and_active_tab(
    data_dir: Path,
) -> None:
    """Financeiro is a real sub-tab as of issue 15, not a placeholder: the
    route must still return 200 with the student's name and mark the tab
    active (see test_financeiro.py for the plan/indicators coverage)."""
    with TestClient(app) as client:
        profile_url = _create_aluno(client, {"name": "Maria Silva"})
        response = client.get(f"{profile_url}/financeiro")

    assert response.status_code == 200
    assert "Maria Silva" in response.text

    aluno_id = profile_url.rsplit("/", 1)[-1]
    active_link = re.search(
        rf'<a class="([^"]*)" href="/alunos/{aluno_id}/financeiro">', response.text
    )
    assert active_link is not None, "financeiro link should exist as an <a> tag"
    assert "on" in active_link.group(1).split()


def test_perfil_route_body_has_no_coming_soon_marker(data_dir: Path) -> None:
    with TestClient(app) as client:
        profile_url = _create_aluno(client, {"name": "Maria Silva"})
        response = client.get(profile_url)

    assert response.status_code == 200
    assert "coming-soon" not in response.text
    assert "por construir" not in response.text


def test_subnav_avaliacoes_link_has_no_coming_soon_marker(data_dir: Path) -> None:
    """Avaliações is no longer a placeholder, so its sub-nav link must not
    carry the "em breve" marker."""
    with TestClient(app) as client:
        profile_url = _create_aluno(client, {"name": "Maria Silva"})
        response = client.get(profile_url)

    nav_match = re.search(r"<nav[^>]*subnav[^>]*>(.*?)</nav>", response.text, re.DOTALL)
    assert nav_match is not None
    nav_html = nav_match.group(1)

    aluno_id = profile_url.rsplit("/", 1)[-1]
    tab_link = re.search(
        rf'<a[^>]*href="/alunos/{aluno_id}/avaliacoes"[^>]*>(.*?)</a>',
        nav_html,
        re.DOTALL,
    )
    assert tab_link is not None
    assert "em breve" not in tab_link.group(1)


def test_subnav_financeiro_link_has_no_coming_soon_marker(data_dir: Path) -> None:
    """Financeiro is no longer a placeholder as of issue 15, so its sub-nav
    link must not carry the "em breve" marker anymore."""
    with TestClient(app) as client:
        profile_url = _create_aluno(client, {"name": "Maria Silva"})
        response = client.get(profile_url)

    nav_match = re.search(r"<nav[^>]*subnav[^>]*>(.*?)</nav>", response.text, re.DOTALL)
    assert nav_match is not None
    nav_html = nav_match.group(1)

    aluno_id = profile_url.rsplit("/", 1)[-1]
    tab_link = re.search(
        rf'<a[^>]*href="/alunos/{aluno_id}/financeiro"[^>]*>(.*?)</a>',
        nav_html,
        re.DOTALL,
    )
    assert tab_link is not None
    assert "em breve" not in tab_link.group(1)


def test_subnav_perfil_link_has_no_coming_soon_marker(data_dir: Path) -> None:
    with TestClient(app) as client:
        profile_url = _create_aluno(client, {"name": "Maria Silva"})
        response = client.get(profile_url)

    nav_match = re.search(r"<nav[^>]*subnav[^>]*>(.*?)</nav>", response.text, re.DOTALL)
    assert nav_match is not None
    nav_html = nav_match.group(1)

    aluno_id = profile_url.rsplit("/", 1)[-1]
    perfil_link = re.search(
        rf'<a[^>]*href="/alunos/{aluno_id}">(.*?)</a>', nav_html, re.DOTALL
    )
    assert perfil_link is not None
    assert "em breve" not in perfil_link.group(1)


def test_unknown_id_avaliacoes_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999/avaliacoes")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_unknown_id_feedback_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999/feedback")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_unknown_id_agenda_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999/agenda")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_unknown_id_financeiro_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999/financeiro")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_edit_route_still_returns_200_not_swallowed_by_subtab_routes(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        profile_url = _create_aluno(client, {"name": "Maria Silva"})
        response = client.get(f"{profile_url}/editar")

    assert response.status_code == 200


def test_novo_route_still_returns_200_not_swallowed_by_subtab_routes(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/novo")

    assert response.status_code == 200
    assert "Novo aluno" in response.text
