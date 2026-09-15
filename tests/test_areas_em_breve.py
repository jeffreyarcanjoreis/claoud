"""Tests for issue 06 / issue 15: áreas "em breve" (Conteúdo & Comunicação)
and the Financeiro area (no longer "em breve" as of issue 15).

Covers the functional specification:
- GET /avaliacao-inicial and GET /conteudo each return 200 (regression: the
  shell's links to these areas no longer 404);
- /conteudo shows the area's name in the h1 and the reusable "em breve" body
  (the "por construir" sentence / the ".coming-soon" wrapper) and at least
  one item from its sketch ("Biblioteca");
- the matching top tab is marked active (class "on" on the corresponding
  <a href="...">) on /conteudo;
- /avaliacao-inicial redirects to / (issue 20 moved the follow-up into the
  Início page itself);
- /financeiro is no longer an "em breve" placeholder: it renders the panel's
  financial indicators (issue 15).

Same isolation pattern as tests/test_shell_painel.py: KAIROS_DATA_DIR points
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


AREAS = (
    ("/conteudo", "Conteúdo &amp; Comunicação"),
)


def test_shell_links_no_longer_404(data_dir: Path) -> None:
    """Regression: the shell's three placeholder links used to 404."""
    with TestClient(app) as client:
        for path, _ in AREAS:
            response = client.get(path)
            assert response.status_code == 200, f"{path} should not 404"


@pytest.mark.parametrize("path", ["/conteudo"])
def test_area_route_returns_200(path: str, data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("path", "title"),
    [
        ("/conteudo", "Conteúdo &amp; Comunicação"),
    ],
)
def test_area_page_shows_area_name_in_h1(path: str, title: str, data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200
    h1_match = re.search(r"<h1>(.*?)</h1>", response.text, re.S)
    assert h1_match is not None
    assert h1_match.group(1).strip() == title


@pytest.mark.parametrize("path", ["/conteudo"])
def test_area_page_shows_coming_soon_body(path: str, data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200
    assert 'class="coming-soon"' in response.text
    assert "por construir" in response.text


def test_avaliacao_inicial_redirects_to_inicio(data_dir: Path) -> None:
    """A Avaliação Inicial deixou de ser área própria: issue 20 recolheu o
    acompanhamento de contatos para o Início (uma seção da própria página),
    então a rota antiga redireciona para lá."""
    with TestClient(app) as client:
        response = client.get("/avaliacao-inicial", follow_redirects=False)

    assert response.status_code in (307, 308, 302, 303)
    assert response.headers["location"] == "/"


def test_financeiro_shows_real_indicators_not_coming_soon(data_dir: Path) -> None:
    """Issue 15/19: /financeiro is no longer a placeholder page -- it
    renders the Resultado do mês in destaque plus the entradas×saídas and
    projeção charts, with access to Recebimentos/Despesas."""
    with TestClient(app) as client:
        response = client.get("/financeiro")

    assert response.status_code == 200
    assert "Resultado do mês" in response.text
    assert "R$" in response.text
    # The next pieces of the épico are still listed as upcoming.
    assert "Recebimentos" in response.text
    assert "Despesas" in response.text


def test_conteudo_shows_sketch_items(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/conteudo")

    assert response.status_code == 200
    assert "Biblioteca" in response.text


@pytest.mark.parametrize("path", ["/conteudo"])
def test_matching_top_tab_is_active(path: str, data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200

    link_match = re.search(rf'<a[^>]*href="{re.escape(path)}"[^>]*>', response.text)
    assert link_match is not None
    classes = link_match.group(0).split("class=")[1].split('"')[1].split()
    assert "on" in classes

    other_paths = [p for p, _ in AREAS if p != path] + ["/", "/alunos"]
    for other in other_paths:
        other_match = re.search(rf'<a[^>]*href="{re.escape(other)}"[^>]*>', response.text)
        assert other_match is not None
        other_classes = other_match.group(0).split("class=")[1].split('"')[1].split()
        assert "on" not in other_classes
