"""Tests for issue 23: the ``POST /contatos/{id}/converter`` route, which
transforms a lead (Contato) into a student (Aluno) with the profile already
filled in.

Covers the functional specification:
- POST /contatos/{id}/converter for an existing lead creates the Aluno and
  redirects (303) to /alunos/{new_id}, which then shows the lead's data;
- following the redirect lands on the new student's own profile page;
- after converting, the lead no longer shows up on GET / (the panel's list
  of open/new contacts);
- POST /contatos/{id}/converter for a non-existent id responds 404.

Same isolation pattern as the other route suites: KAIROS_DATA_DIR points at
a temp dir and the cached engine is disposed on teardown.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.contatos.service import create_cadastro, create_contato
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_converter_route_creates_aluno_and_redirects_to_its_profile(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        lead = create_cadastro(
            nome="Julia Prado",
            contato="julia@example.com",
            objetivo="Emagrecimento",
            consentimento=True,
        )

        response = client.post(
            f"/contatos/{lead['id']}/converter", follow_redirects=False
        )

    assert response.status_code == 303
    assert re.fullmatch(r"/alunos/\d+", response.headers["location"])


def test_following_the_redirect_shows_the_new_student_profile(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        lead = create_cadastro(
            nome="Julia Prado",
            contato="julia@example.com",
            objetivo="Emagrecimento",
            consentimento=True,
        )

        response = client.post(
            f"/contatos/{lead['id']}/converter", follow_redirects=True
        )

    assert response.status_code == 200
    assert re.search(r"/alunos/\d+", str(response.url))
    assert "Julia Prado" in response.text
    assert "Emagrecimento" in response.text


def test_converted_lead_no_longer_appears_in_new_contacts_list(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        lead = create_contato(nome="Convertida")
        client.post(f"/contatos/{lead['id']}/converter", follow_redirects=False)

        inicio = client.get("/")

    assert inicio.status_code == 200
    assert "Convertida" not in inicio.text


def test_converter_route_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/contatos/9999/converter", follow_redirects=False)

    assert response.status_code == 404
