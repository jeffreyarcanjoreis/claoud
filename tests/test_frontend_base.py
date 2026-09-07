"""Tests for issue 01: brand tokens, base CSS and self-hosted fonts.

Covers the functional specification:
- the FastAPI app serves static files under /static/... (existing file -> 200,
  missing file -> 404 without breaking the app);
- /static/css/tokens.css and /static/css/base.css exist and respond 200 with
  a CSS content type;
- any page that extends base.html loads both stylesheets in the <head>;
- that same page does not reference fonts.googleapis.com or gstatic (proof
  that Fraunces and Archivo are self-hosted);
- at least one font file exists under /static/fonts/ and is served with 200.

Same isolation pattern as tests/test_lista_alunos.py: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.main import app

_STATIC_FONTS_DIR = Path(__file__).resolve().parent.parent / "kairos" / "static" / "fonts"


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_tokens_css_is_served_with_200(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/static/css/tokens.css")

    assert response.status_code == 200
    assert "css" in response.headers["content-type"]


def test_base_css_is_served_with_200(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/static/css/base.css")

    assert response.status_code == 200
    assert "css" in response.headers["content-type"]


def test_page_using_base_html_links_both_stylesheets(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200
    # os estáticos levam um ?v={{ asset_ver }} (cache-busting por versão)
    assert 'href="/static/css/tokens.css?v=' in response.text
    assert 'href="/static/css/base.css?v=' in response.text


def test_page_does_not_reference_external_font_cdns(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200
    assert "fonts.googleapis.com" not in response.text
    assert "gstatic" not in response.text


def test_a_font_file_is_served_from_static_fonts(data_dir: Path) -> None:
    font_files = sorted(_STATIC_FONTS_DIR.glob("*.woff2"))
    assert font_files, "Expected at least one .woff2 file in kairos/static/fonts/"

    font_name = font_files[0].name
    with TestClient(app) as client:
        response = client.get(f"/static/fonts/{font_name}")

    assert response.status_code == 200


def test_nonexistent_static_file_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/static/css/nao-existe.css")

    assert response.status_code == 404
