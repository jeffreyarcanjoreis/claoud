"""Tests for issue 27: the Avaliação Inicial opens in a modal on the vitrine,
submitted via fetch (AJAX), instead of only through the standalone
``/comecar`` page.

Covers the functional specification:
- POST /comecar with an "Accept: application/json" header (or
  "X-Requested-With: fetch") and valid data + consentimento="on" creates the
  lead and responds 200 with JSON {"ok": true} -- no HTML re-render;
- POST /comecar with that header and invalid data (e.g. missing
  consentimento) does NOT create the lead and responds 400 with JSON
  {"ok": false, "error": "<non-empty message>"};
- POST /comecar WITHOUT that header keeps the pre-existing HTML fallback
  behaviour unchanged: 200 + "Recebido!" on success, 400 + re-rendered form
  on error;
- GET /comecar keeps rendering the sign-up form (the partial used by both
  the standalone page and the vitrine modal).

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


VALID_PAYLOAD = {
    "nome": "Renata Alves",
    "contato": "renata@example.com",
    "idade": "29",
    "sexo": "feminino",
    "objetivo": "Ganhar força",
    "frequencia_desejada": "3-4",
    "nivel_condicionamento": "iniciante",
    "consentimento": "on",
}


# ---------------------------------------------------------------------------
# POST /comecar -- JSON path (Accept: application/json)
# ---------------------------------------------------------------------------


def test_post_comecar_json_with_valid_data_creates_lead_and_returns_ok_true(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/comecar",
            data=VALID_PAYLOAD,
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    abertos = list_contatos_abertos()
    assert len(abertos) == 1
    lead = abertos[0]
    assert lead["nome"] == "Renata Alves"
    assert lead["contato"] == "renata@example.com"
    assert lead["origem"] == "cadastro"


def test_post_comecar_json_without_consentimento_returns_400_with_error_and_no_lead(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/comecar",
            data={"nome": "Sergio Matos", "contato": "sergio@example.com"},
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert isinstance(body["error"], str)
    assert body["error"] != ""

    assert list_contatos_abertos() == []


def test_post_comecar_via_x_requested_with_header_also_returns_json(
    data_dir: Path,
) -> None:
    """The fetch-based trigger can identify itself either via Accept or via
    X-Requested-With: fetch -- both are accepted as "wants JSON"."""
    with TestClient(app) as client:
        response = client.post(
            "/comecar",
            data=VALID_PAYLOAD,
            headers={"X-Requested-With": "fetch"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(list_contatos_abertos()) == 1


# ---------------------------------------------------------------------------
# POST /comecar -- HTML fallback path (no Accept: application/json header)
# ---------------------------------------------------------------------------


def test_post_comecar_html_fallback_success_unchanged(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/comecar", data=VALID_PAYLOAD)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Recebido!" in response.text
    assert len(list_contatos_abertos()) == 1


def test_post_comecar_html_fallback_error_unchanged(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/comecar",
            data={"nome": "Sergio Matos", "contato": "sergio@example.com"},
        )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("text/html")
    assert "autorizar" in response.text
    assert list_contatos_abertos() == []


# ---------------------------------------------------------------------------
# GET /comecar -- still renders the (partial-based) form
# ---------------------------------------------------------------------------


def test_get_comecar_still_renders_the_form_fields(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/comecar")

    assert response.status_code == 200
    body = response.text
    assert 'name="nome"' in body
    assert 'name="contato"' in body
    assert 'name="consentimento"' in body
