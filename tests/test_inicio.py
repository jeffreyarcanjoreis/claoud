"""Tests for issue 05: Início do painel com contagens.

Covers the functional specification:
- GET / renders the Início page with status 200 (no longer a redirect);
- the Início tab (<a href="/">) is marked active on /;
- the Início page shows real counts read from the database: total students
  and active students (creating N students, M active, and asserting the
  numbers shown);
- with zero students, the counts show 0 (not "em breve" — 0 is real data);
- the "Novos contatos" tile shows the real open contacts count, never an
  invented number (see tests/test_inicio_contatos.py for the full contatos
  coverage added by issue 20).

The "Sessões de hoje" tile was upgraded to a real, linked count by issue 06
(see tests/test_agenda_global.py); the "Financeiro" tile was upgraded to show
the real MRR by issue 15 (see tests/test_financeiro.py); the "Novos contatos"
tile was upgraded from an "em breve" placeholder to a real count by issue 20;
the assertions here were updated to match those intentional behavior changes.

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


def test_root_returns_200_and_shows_inicio(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.history == []  # no redirect happened
    assert "Visão geral" in response.text
    assert "Bom te ver" in response.text


def test_inicio_tab_is_active_on_root(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200

    inicio_link = re.search(r'<a[^>]*href="/"[^>]*>', response.text)
    assert inicio_link is not None
    inicio_classes = inicio_link.group(0).split("class=")[1].split('"')[1].split()
    assert "on" in inicio_classes


def test_shows_real_counts_for_total_and_active_students(data_dir: Path) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data={"name": "Ana Lima", "status": "active"})
        client.post("/alunos", data={"name": "Bruno Costa", "status": "active"})
        client.post("/alunos", data={"name": "Carla Souza", "status": "inactive"})

        response = client.get("/")

    assert response.status_code == 200

    total_match = re.search(
        r'<div class="n">\s*(\d+)\s*</div>\s*<div class="l">Alunos</div>',
        response.text,
    )
    assert total_match is not None
    assert total_match.group(1) == "3"

    active_match = re.search(
        r'<div class="n gold">\s*(\d+)\s*</div>\s*<div class="l">Ativos</div>',
        response.text,
    )
    assert active_match is not None
    assert active_match.group(1) == "2"


def test_zero_students_shows_zero_not_em_breve(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200

    total_match = re.search(
        r'<div class="n">\s*(\d+)\s*</div>\s*<div class="l">Alunos</div>',
        response.text,
    )
    assert total_match is not None
    assert total_match.group(1) == "0"

    active_match = re.search(
        r'<div class="n gold">\s*(\d+)\s*</div>\s*<div class="l">Ativos</div>',
        response.text,
    )
    assert active_match is not None
    assert active_match.group(1) == "0"


def test_stat_tiles_are_clickable_links(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200

    assert '<a class="stat" href="/alunos">' in response.text
    assert '<a class="stat" href="/alunos?status=active">' in response.text
    assert '<a class="stat" href="/financeiro">' in response.text

    # Issue 06 upgraded "Sessões de hoje" from a placeholder to a real,
    # clickable tile linking to /agenda.
    assert '<a class="stat" href="/agenda">' in response.text

    # Novos contatos (leads): issue 20 moved this follow-up into the Início
    # page itself (a toggle-able section), not a link to another area.
    assert "Novos contatos" in response.text


def test_novos_contatos_tile_shows_real_count_not_em_breve(data_dir: Path) -> None:
    """Issue 15 upgraded the "Financeiro" tile to show the real MRR; issue 20
    upgraded the "Novos contatos" tile as well -- it now shows the real open
    contacts count (contatos | length), never an "em breve" placeholder."""
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert '<div class="soon">' not in response.text

    novos_contatos_match = re.search(
        r'<div class="n">\s*0\s*</div>\s*<div class="l">Novos contatos</div>',
        response.text,
    )
    assert novos_contatos_match is not None
