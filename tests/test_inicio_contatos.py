"""Tests for issue 20/22: the "Novos contatos" follow-up on the Início page.

Covers the functional specification:
- GET / shows the "Novos contatos" tile with the count of open contacts
  (contatos | length) and the toggle-able <section class="contatos">;
- with zero contacts, the count shown is 0 (not "em breve" -- issue 20
  upgrades this tile from a placeholder to a real, if still simple, count);
- the "Avaliação Inicial" central area links to the native public sign-up
  page (``/comecar``, "Compartilhar o cadastro") -- issue 22 replaces the
  Google Form/Sheet "Configure ..." placeholder states entirely;
- with a contact created via the service layer, its name appears in the
  Início contact list, and each contact card has a "ver" link pointing at
  its lead detail page (``/contatos/{id}``).

Same isolation pattern as tests/test_inicio.py: KAIROS_DATA_DIR points at a
temp dir and the cached engine is disposed on teardown.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.contatos.service import create_contato
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_inicio_shows_contatos_tile_with_count_and_section(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    text = response.text
    assert 'class="contatos"' in text

    count_match = re.search(
        r'<div class="n">\s*(\d+)\s*</div>\s*<div class="l">Novos contatos</div>',
        text,
    )
    assert count_match is not None
    assert count_match.group(1) == "0"


def test_inicio_contatos_count_reflects_open_contacts(data_dir: Path) -> None:
    with TestClient(app) as client:
        create_contato(nome="Marcia Alves")
        create_contato(nome="Nuno Ferreira")

        response = client.get("/")

    count_match = re.search(
        r'<div class="n">\s*(\d+)\s*</div>\s*<div class="l">Novos contatos</div>',
        response.text,
    )
    assert count_match is not None
    assert count_match.group(1) == "2"


def test_inicio_shows_created_contact_in_the_list(data_dir: Path) -> None:
    with TestClient(app) as client:
        create_contato(nome="Otavio Ramos", contato="otavio@example.com")

        response = client.get("/")

    assert "Otavio Ramos" in response.text
    assert "otavio@example.com" in response.text


def test_inicio_contato_card_has_ver_link_to_lead_detail(data_dir: Path) -> None:
    with TestClient(app) as client:
        created = create_contato(nome="Paula Nogueira")

        response = client.get("/")

    assert f'href="/contatos/{created["id"]}"' in response.text
    assert ">ver<" in response.text


def test_inicio_central_links_to_the_native_sign_up_page(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert 'href="/comecar"' in response.text
    assert "Compartilhar o cadastro" in response.text
