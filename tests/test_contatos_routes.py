"""Tests for issue 20: the "contatos" (lightweight contact follow-up) HTTP
routes.

Covers the functional specification:
- POST /contatos with a valid name creates the contact and redirects (303)
  to /; the new contact then shows up on GET /;
- POST /contatos without a name re-renders the Início page with 400 and
  shows the error message ("Nome é obrigatório.");
- POST /contatos/{id}/status changes the contact's status and redirects
  (303) to /; an invalid status returns 400 with the error message;
- POST /contatos/{id}/remover removes the contact and redirects (303) to /;
- updating the status of, or removing, a non-existent id returns 404.

Same isolation pattern as tests/test_tarefas.py: KAIROS_DATA_DIR points at a
temp dir and the cached engine is disposed on teardown.
"""

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


def test_post_contatos_valid_redirects_and_appears_on_inicio(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/contatos",
            data={"nome": "Isabela Nunes", "contato": "", "observacao": ""},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        follow_up = client.get("/")

    assert "Isabela Nunes" in follow_up.text


def test_post_contatos_without_nome_returns_400_and_shows_error(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/contatos",
            data={
                "nome": "",
                "contato": "(11) 98888-1111",
                "observacao": "Nota qualquer",
            },
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Nome é obrigatório." in response.text
    assert "(11) 98888-1111" in response.text


def test_post_contatos_status_updates_the_status(data_dir: Path) -> None:
    with TestClient(app) as client:
        contato = create_contato(nome="Joao Pedro")

        response = client.post(
            f"/contatos/{contato['id']}/status",
            data={"status": "conversando"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        follow_up = client.get("/")

    assert "Conversando" in follow_up.text


def test_post_contatos_status_invalid_returns_400(data_dir: Path) -> None:
    with TestClient(app) as client:
        contato = create_contato(nome="Karina Lopes")

        response = client.post(
            f"/contatos/{contato['id']}/status",
            data={"status": "xpto"},
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Status inválido." in response.text


def test_post_contatos_remover_redirects_and_removes_from_inicio(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        contato = create_contato(nome="Lucas Martins")

        response = client.post(
            f"/contatos/{contato['id']}/remover", follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/"

        follow_up = client.get("/")

    assert "Lucas Martins" not in follow_up.text


def test_post_contatos_status_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/contatos/9999/status",
            data={"status": "conversando"},
            follow_redirects=False,
        )

    assert response.status_code == 404


def test_post_contatos_remover_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/contatos/9999/remover", follow_redirects=False)

    assert response.status_code == 404
