"""Tests for issue 22: the native public sign-up page (``/comecar``), which
replaces the Google Form as the way a prospective student becomes a lead
(Contato), collecting the full student profile -- including health data --
under the person's explicit consent.

Covers the functional specification:
- GET /comecar responds 200 with a standalone page (its own <html>, not the
  panel's shell) containing the sign-up form, the required nome/contato
  fields, the consentimento checkbox and the sexo/nivel_condicionamento/
  frequencia_desejada selects;
- POST /comecar with valid data and consentimento="on" creates the lead
  (Contato) with origem="cadastro" and shows the "Recebido!" confirmation;
- POST /comecar without consentimento does not create the lead and
  re-renders the form with a 400 status and an error message;
- POST /comecar without nome/contato does not create the lead and
  re-renders the form with a 400 status and an error message;
- the lead created through /comecar is visible through the service layer
  (list_contatos_abertos) with origem "cadastro".

Same isolation pattern as the other route suites: KAIROS_DATA_DIR points at
a temp dir and the cached engine is disposed on setup/teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.contatos.service import list_contatos_abertos
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# GET /comecar
# ---------------------------------------------------------------------------


def test_get_comecar_returns_200_with_the_sign_up_form(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/comecar")

    assert response.status_code == 200
    body = response.text
    assert '<form method="post" action="/comecar"' in body
    assert 'name="nome"' in body
    assert 'name="contato"' in body
    assert 'name="consentimento"' in body
    assert 'name="sexo"' in body
    assert 'name="nivel_condicionamento"' in body
    assert 'name="frequencia_desejada"' in body


def test_get_comecar_is_a_standalone_page_without_panel_shell(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/comecar")

    body = response.text
    assert "<html" in body
    assert 'class="tabs"' not in body
    assert "painel do coach" not in body


# ---------------------------------------------------------------------------
# POST /comecar
# ---------------------------------------------------------------------------


def test_post_comecar_with_valid_data_creates_the_lead_and_shows_confirmation(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/comecar",
            data={
                "nome": "Renata Alves",
                "contato": "renata@example.com",
                "idade": "29",
                "sexo": "feminino",
                "objetivo": "Ganhar força",
                "frequencia_desejada": "3-4",
                "nivel_condicionamento": "iniciante",
                "consentimento": "on",
            },
        )

    assert response.status_code == 200
    assert "Recebido!" in response.text

    abertos = list_contatos_abertos()
    assert len(abertos) == 1
    lead = abertos[0]
    assert lead["nome"] == "Renata Alves"
    assert lead["contato"] == "renata@example.com"
    assert lead["origem"] == "cadastro"
    assert lead["consentimento"] is True


def test_post_comecar_without_consentimento_does_not_create_lead_and_returns_400(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/comecar",
            data={
                "nome": "Sergio Matos",
                "contato": "sergio@example.com",
            },
        )

    assert response.status_code == 400
    assert "autorizar" in response.text
    assert list_contatos_abertos() == []


def test_post_comecar_without_nome_does_not_create_lead_and_returns_400(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/comecar",
            data={
                "contato": "sem-nome@example.com",
                "consentimento": "on",
            },
        )

    assert response.status_code == 400
    assert list_contatos_abertos() == []


def test_post_comecar_without_contato_does_not_create_lead_and_returns_400(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/comecar",
            data={
                "nome": "Tania Ferro",
                "consentimento": "on",
            },
        )

    assert response.status_code == 400
    assert list_contatos_abertos() == []


def test_post_comecar_with_invalid_data_re_renders_the_form(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/comecar",
            data={
                "nome": "",
                "contato": "",
                "consentimento": "on",
            },
        )

    assert response.status_code == 400
    assert '<form method="post" action="/comecar"' in response.text
