"""Tests for issue 22: the lead detail page (``GET /contatos/{id}``), which
shows a lead's (Contato's) full profile, as submitted through the native
public sign-up form (``/comecar``).

Covers the functional specification:
- GET /contatos/{id} for an existing lead responds 200 and shows the lead's
  name and at least one filled-in profile field (e.g. objetivo);
- fields that were left empty at sign-up show a "sem registro" placeholder
  instead of a blank or fabricated value (architecture rule 6);
- GET /contatos/{id} for a non-existent id responds 404.

Same isolation pattern as the other route suites: KAIROS_DATA_DIR points at
a temp dir and the cached engine is disposed on setup/teardown.
"""

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


def test_lead_detalhe_shows_name_and_filled_field(data_dir: Path) -> None:
    with TestClient(app) as client:
        lead = create_cadastro(
            nome="Ursula Pinto",
            contato="ursula@example.com",
            objetivo="Reabilitação de joelho",
            consentimento=True,
        )

        response = client.get(f"/contatos/{lead['id']}")

    assert response.status_code == 200
    body = response.text
    assert "Ursula Pinto" in body
    assert "Reabilitação de joelho" in body


def test_lead_detalhe_shows_sem_registro_for_empty_fields(data_dir: Path) -> None:
    with TestClient(app) as client:
        lead = create_contato(nome="Vitor Nogueira")

        response = client.get(f"/contatos/{lead['id']}")

    assert response.status_code == 200
    assert "sem registro" in response.text


def test_lead_detalhe_returns_404_for_unknown_id(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/contatos/9999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# issue 23: "Transformar em aluno" button
# ---------------------------------------------------------------------------


def test_lead_detalhe_shows_transformar_em_aluno_button_when_open(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        lead = create_contato(nome="Convertivel")

        response = client.get(f"/contatos/{lead['id']}")

    assert response.status_code == 200
    assert f'action="/contatos/{lead["id"]}/converter"' in response.text
    assert "Transformar em aluno" in response.text


def test_lead_detalhe_hides_transformar_em_aluno_button_when_already_aluno(
    data_dir: Path,
) -> None:
    from kairos.contatos.service import atualizar_status

    with TestClient(app) as client:
        lead = create_contato(nome="Ja Convertida")
        atualizar_status(lead["id"], "virou_aluno")

        response = client.get(f"/contatos/{lead['id']}")

    assert response.status_code == 200
    assert "Transformar em aluno" not in response.text
