"""Tests for the "nivel" (student self-recognized level) domain -- issue 03
(student side: self-recognition in the aluno's own area).

Covers the functional specification:

Student side (``/aluno/nivel``, session-scoped ``aluno_id``):
- ``GET /aluno/nivel`` renders 200, showing "Meu nível", the four level
  options (``NIVEL_LABELS``) and the student's own frente (label +
  significado from ``get_aluno``, resolved from issue 01), or "sem registro"
  plus an invitation to talk to the coach when the aluno has no frente yet;
- ``POST /aluno/nivel`` with a valid ``nivel`` (and optional ``nota``)
  redirects (303) to ``/aluno/nivel`` and persists a new self-recognition
  under the session's aluno via ``kairos.nivel.service.reconhecer``;
- recognizing again (even a different level) grows the history -- this is
  never an upsert -- and ``nivel_atual`` reflects the most recent
  recognition; the GET page highlights the current level (radio ``checked``);
- an invalid ``nivel`` is rejected (not 303) and nothing is persisted;
- ``nota`` is normalized: surrounding whitespace is stripped, and an
  empty/whitespace-only value becomes ``None``;
- isolation: the self-recognition is always scoped to the session's
  aluno_id, never to another aluno.

Isolation: KAIROS_DATA_DIR points at a temp dir and the cached engine is
disposed on setup/teardown (same pattern as tests/test_registro_treino.py
and tests/test_checkin.py); the suite-wide ``_no_remote_database_url``
autouse fixture (see tests/conftest.py) already keeps KAIROS_DATABASE_URL
out of the picture.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno, set_frente
from kairos.main import app
from kairos.nivel.service import (
    NIVEL_LABELS,
    list_reconhecimentos,
    nivel_atual,
    reconhecer,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def _login_as_aluno(monkeypatch: pytest.MonkeyPatch, aluno_id) -> None:
    """Override the suite-wide auto-login-as-coach patch with a student
    session for the current test.

    Patches the gate's own reference (``kairos.auth.middleware``), the
    student home route's directly-imported reference
    (``kairos.area_aluno.routes``), and the nivel routes' directly-imported
    reference (``kairos.nivel.routes``): each ``from ... import
    current_user`` binds a separate name that a patch on the origin module
    does not reach.
    """
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)
    monkeypatch.setattr("kairos.nivel.routes.current_user", fake_current_user)


# ---------------------------------------------------------------------------
# 1. GET /aluno/nivel renders
# ---------------------------------------------------------------------------


def test_get_aluno_nivel_renders_form_with_all_four_levels(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/nivel")

    assert response.status_code == 200
    assert "Meu nível" in response.text
    assert NIVEL_LABELS["fundacao"] in response.text
    assert NIVEL_LABELS["construcao"] in response.text
    assert NIVEL_LABELS["dominio"] in response.text
    assert NIVEL_LABELS["maestria"] in response.text


# ---------------------------------------------------------------------------
# 2. Frente display: "sem registro" vs the aluno's actual frente
# ---------------------------------------------------------------------------


def test_get_aluno_nivel_shows_sem_registro_when_aluno_has_no_frente(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/nivel")

    assert response.status_code == 200
    assert "sem registro" in response.text


def test_get_aluno_nivel_shows_frente_label_when_aluno_has_a_frente(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        set_frente(aluno["id"], "saude_integrada")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/nivel")

    assert response.status_code == 200
    assert "Saúde Integrada" in response.text
    assert "sem registro" not in response.text


# ---------------------------------------------------------------------------
# 3. POST /aluno/nivel with a valid nivel persists and redirects
# ---------------------------------------------------------------------------


def test_post_aluno_nivel_with_valid_nivel_redirects_and_persists(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/nivel",
            data={"nivel": "construcao", "nota": "Sinto que evoluí."},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/aluno/nivel"

        historico = list_reconhecimentos(aluno["id"])

    assert len(historico) == 1
    assert historico[0]["nivel"] == "construcao"
    assert historico[0]["nota"] == "Sinto que evoluí."


# ---------------------------------------------------------------------------
# 4. Recognizing again grows history; nivel_atual reflects the most recent
# ---------------------------------------------------------------------------


def test_post_aluno_nivel_again_grows_history_and_updates_current_level(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        client.post(
            "/aluno/nivel", data={"nivel": "construcao"}, follow_redirects=False
        )
        response = client.post(
            "/aluno/nivel", data={"nivel": "dominio"}, follow_redirects=False
        )

        assert response.status_code == 303

        historico = list_reconhecimentos(aluno["id"])
        atual = nivel_atual(aluno["id"])

        pagina = client.get("/aluno/nivel")

    assert len(historico) == 2
    assert atual is not None
    assert atual["nivel"] == "dominio"

    # The current level's radio comes pre-checked on the GET page.
    assert pagina.status_code == 200
    assert (
        'value="dominio" checked' in pagina.text
        or 'value="dominio"  checked' in pagina.text
    )


# ---------------------------------------------------------------------------
# 5. Invalid nivel is rejected: not 303, nothing persisted
# ---------------------------------------------------------------------------


def test_post_aluno_nivel_with_invalid_nivel_does_not_redirect_and_saves_nothing(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/nivel", data={"nivel": "xpto"}, follow_redirects=False
        )

    assert response.status_code != 303
    assert response.status_code == 400
    assert "location" not in response.headers
    assert list_reconhecimentos(aluno["id"]) == []


# ---------------------------------------------------------------------------
# 6. nota normalization: whitespace stripped / blank becomes None
# ---------------------------------------------------------------------------


def test_post_aluno_nivel_strips_surrounding_whitespace_from_nota(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/nivel",
            data={"nivel": "fundacao", "nota": "  Me sinto mais confiante.  "},
            follow_redirects=False,
        )

        assert response.status_code == 303
        historico = list_reconhecimentos(aluno["id"])

    assert historico[0]["nota"] == "Me sinto mais confiante."


def test_post_aluno_nivel_with_blank_nota_stores_none(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/nivel",
            data={"nivel": "fundacao", "nota": "   "},
            follow_redirects=False,
        )

        assert response.status_code == 303
        historico = list_reconhecimentos(aluno["id"])

    assert historico[0]["nota"] is None


# ---------------------------------------------------------------------------
# 7. Isolation: always scoped to the session's aluno_id
# ---------------------------------------------------------------------------


def test_post_aluno_nivel_always_writes_to_the_session_aluno_never_another(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        reconhecer(aluno_b["id"], nivel="maestria")

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.post(
            "/aluno/nivel", data={"nivel": "fundacao"}, follow_redirects=False
        )

        assert response.status_code == 303

        historico_a = list_reconhecimentos(aluno_a["id"])
        historico_b = list_reconhecimentos(aluno_b["id"])

    assert len(historico_a) == 1
    assert historico_a[0]["nivel"] == "fundacao"
    assert len(historico_b) == 1
    assert historico_b[0]["nivel"] == "maestria"  # unchanged by aluno A's POST
