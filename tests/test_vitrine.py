"""Tests for issue 21 (vitrine — abas / expanded public showcase).

Covers the functional specification:
- GET /vitrine responds 200 with an HTML page containing the slogan, the
  subtitle, the "Começar" CTA, the "Entrar" link (-> /login, since issue 26
  Fase 1 gates "/" behind a coach session), the 3D logo canvas
  (#vitrine-logo) and the vitrine-hero.js script;
- GET /vitrine is a standalone page: it does NOT reuse the panel's shell
  (no tabs navigation, no "painel do coach" topbar);
- GET / keeps working as the coach's panel (untouched by the new route);
- The top menu has anchor links to the #metodo and #profissionais sections;
  the "Começar" CTA no longer anchors to #vamos-comecar -- issue 27 makes it
  open the sign-up modal instead (href="/comecar" + data-abre-cadastro);
- Section "metodo" (id="metodo") carries the opening line and at least one
  of its content blocks;
- Section "profissionais" (id="profissionais") mentions Jeffrey Reis;
- Section "vamos-comecar" (id="vamos-comecar") always renders the native
  public sign-up CTA -- href="/comecar" + "Fazer a Avaliação Inicial" --
  issue 22 replaces the Google Form and its "configured or not" states with
  the native page, always available;
- Issue 27: the Avaliação Inicial opens in a modal on the vitrine (AJAX
  submission), on top of the standalone /comecar page (fallback without JS).
  The page renders a modal (class="v-modal") with the sign-up form partial
  (name="nome", name="contato", name="consentimento" fields), and at least
  one element with the ``data-abre-cadastro`` trigger attribute.

Same isolation pattern as the other route suites: KAIROS_DATA_DIR points at
a temp dir and the cached engine is disposed on setup/teardown, even though
/vitrine itself doesn't touch the database (the app's lifespan runs
migrations on startup regardless of which route is requested).
"""

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


def test_vitrine_returns_200_with_hero_content(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/vitrine")

    assert response.status_code == 200
    body = response.text
    assert "Mover-se no" in body
    assert "momento certo" in body
    assert "No corpo, na mente, no espírito e na comunidade." in body
    assert "Começar" in body
    # Issue 26 (Fase 1): "/" now requires a coach session, so "Entrar"
    # points at /login (which itself redirects an already-logged-in coach
    # to "/").
    assert 'href="/login"' in body
    assert "Entrar" in body
    assert 'id="vitrine-logo"' in body
    assert "/static/js/vitrine-hero.js" in body


def test_vitrine_entrar_link_points_to_login(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/vitrine")

    assert 'class="entrar" href="/login"' in response.text


def test_vitrine_is_standalone_page_without_panel_shell(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/vitrine")

    body = response.text
    assert 'class="tabs"' not in body
    assert "painel do coach" not in body


def test_painel_root_still_works_untouched(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Bom te ver" in response.text
    assert 'class="tabs"' in response.text


def test_vitrine_has_the_three_sections(data_dir: Path) -> None:
    """The page reaches metodo, profissionais and vamos-comecar sections."""
    with TestClient(app) as client:
        response = client.get("/vitrine")

    body = response.text
    assert 'id="metodo"' in body
    assert 'id="profissionais"' in body
    assert 'id="vamos-comecar"' in body


def test_vitrine_top_menu_has_anchor_links_to_the_sections(data_dir: Path) -> None:
    """The top menu still anchors to #metodo/#profissionais. The "Começar"
    CTA no longer anchors to #vamos-comecar (issue 27): it now opens the
    sign-up modal instead, via href="/comecar" + data-abre-cadastro."""
    with TestClient(app) as client:
        response = client.get("/vitrine")

    body = response.text
    assert 'href="#metodo"' in body
    assert 'href="#profissionais"' in body
    assert 'href="#vamos-comecar"' not in body


def test_vitrine_has_sign_up_modal_with_form_and_trigger(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/vitrine")

    body = response.text
    assert 'class="v-modal"' in body
    assert 'name="nome"' in body
    assert 'name="contato"' in body
    assert 'name="consentimento"' in body
    assert "data-abre-cadastro" in body


def test_vitrine_metodo_section_has_opening_line_and_content_blocks(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/vitrine")

    body = response.text
    assert "Não existe o treino certo" in body
    assert "A jornada, passo a passo" in body or "Como é feito, na prática" in body


def test_vitrine_profissionais_section_mentions_jeffrey_reis(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/vitrine")

    assert "Jeffrey Reis" in response.text


def test_vitrine_vamos_comecar_cta_points_to_native_sign_up_page(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/vitrine")

    body = response.text
    assert "começa agora" in body
    assert 'href="/comecar"' in body
    assert "Fazer a Avaliação Inicial" in body
