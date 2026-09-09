"""Tests for issue 02: shell do painel (top bar and tab navigation).

Covers the functional specification:
- GET /alunos shows the top bar (wordmark "Kairos" + "painel do coach") and
  the five tab labels: Início, Avaliação Inicial, Alunos, Financeiro,
  Conteúdo & Comunicação;
- on /alunos, the Alunos tab is marked active (class "on" on the
  <a href="/alunos">) and the Início tab is not;
- GET / renders Início (issue 05) and the Início tab (<a href="/">) is
  marked active there;
- the tabs' hrefs point to /, /alunos, /avaliacao-inicial, /financeiro,
  /conteudo;
- Avaliação Inicial, Financeiro and Conteúdo & Comunicação show the "em
  breve" marker; Alunos and Início do not;
- the <link> to /static/css/shell.css is present;
- the 404 page (GET /alunos/999) also shows the top bar and the tabs.

Same isolation pattern as tests/test_lista_alunos.py: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on teardown.
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


def test_alunos_page_shows_topbar_and_five_tab_labels(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200
    assert "Kairos" in response.text
    assert "painel do coach" in response.text

    for label in (
        "Início",
        "Alunos",
        "Financeiro",
        "Conteúdo &amp; Comunicação",
    ):
        assert label in response.text


def test_alunos_tab_is_active_and_inicio_tab_is_not(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200

    alunos_link = re.search(r'<a[^>]*href="/alunos"[^>]*>', response.text)
    assert alunos_link is not None
    assert "on" in alunos_link.group(0).split("class=")[1]

    inicio_link = re.search(r'<a[^>]*href="/"[^>]*>', response.text)
    assert inicio_link is not None
    inicio_classes = inicio_link.group(0).split("class=")[1]
    assert "on" not in inicio_classes.split('"')[1].split()


def test_inicio_tab_is_active_on_root(data_dir: Path) -> None:
    # "/" renders Início (issue 05); the Início tab is marked active there.
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 200

    inicio_link = re.search(r'<a[^>]*href="/"[^>]*>', response.text)
    assert inicio_link is not None
    assert "on" in inicio_link.group(0).split("class=")[1].split('"')[1].split()


def test_tab_hrefs_point_to_expected_routes(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200
    for href in (
        'href="/"',
        'href="/alunos"',
        'href="/financeiro"',
        'href="/conteudo"',
    ):
        assert href in response.text


def test_future_tabs_show_em_breve_marker_and_others_do_not(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200
    assert response.text.count("em breve") == 2

    inicio_link = re.search(r'<a[^>]*href="/"[^>]*>.*?</a>', response.text, re.S)
    alunos_link = re.search(r'<a[^>]*href="/alunos"[^>]*>.*?</a>', response.text, re.S)
    assert inicio_link is not None
    assert alunos_link is not None
    assert "em breve" not in inicio_link.group(0)
    assert "em breve" not in alunos_link.group(0)

    for href in ('href="/financeiro"', 'href="/conteudo"'):
        link = re.search(rf'<a[^>]*{re.escape(href)}[^>]*>.*?</a>', response.text, re.S)
        assert link is not None
        assert "em breve" in link.group(0)


def test_shell_css_link_is_present(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200
    assert 'href="/static/css/shell.css?v=' in response.text


def test_404_page_also_shows_topbar_and_tabs(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999")

    assert response.status_code == 404
    assert "painel do coach" in response.text

    for label in (
        "Início",
        "Alunos",
        "Financeiro",
        "Conteúdo &amp; Comunicação",
    ):
        assert label in response.text

    assert 'href="/static/css/shell.css?v=' in response.text
