"""Tests for issue 01 (frente do aluno): the coach classifies a student
under one of three "frentes" (fronts) -- performance, saude_integrada,
longevidade.

Covers the functional specification:

Service layer (``kairos.alunos.service``):
- ``set_frente`` persists a valid frente and ``get_aluno`` reflects it back
  with ``frente``, ``frente_label`` and a non-null ``frente_significado``;
- ``set_frente(id, "")``/``set_frente(id, None)`` clears the frente back to
  None (and the label along with it);
- switching from one frente to another replaces the value (no stacking);
- an invalid frente value raises ``ValidationError`` and persists nothing
  (the aluno keeps whatever frente it had before the failed call);
- ``set_frente`` for a non-existent aluno returns ``None``.

Route ``POST /alunos/{aluno_id}/frente`` (coach auto-logged in by the
suite-wide ``_auto_login_as_coach`` fixture):
- a valid submission redirects (303) to ``/alunos/{id}?atualizado=1`` and
  persists the change;
- a non-existent aluno returns 404;
- an invalid frente re-renders the ficha (perfil tab) with 400 and persists
  nothing.

Ficha ``GET /alunos/{id}``:
- a student with no frente shows "sem registro" in the Frente section, plus
  the ``<select name="frente">`` with its options;
- a student with a frente defined shows its label (e.g. "Saúde Integrada").

Isolation: KAIROS_DATA_DIR points at a temp dir and the cached engine is
disposed on setup/teardown (same pattern as tests/test_checkin.py).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import (
    ValidationError,
    create_aluno,
    get_aluno,
    set_frente,
)
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
# 1. Service: set_frente persists and get_aluno reflects label/significado
# ---------------------------------------------------------------------------


def test_set_frente_persists_and_get_aluno_reflects_label_and_significado(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        result = set_frente(aluno["id"], "performance")

        assert result is not None
        assert result["frente"] == "performance"
        assert result["frente_label"] == "Performance"
        assert result["frente_significado"]

        fetched = get_aluno(aluno["id"])

    assert fetched is not None
    assert fetched["frente"] == "performance"
    assert fetched["frente_label"] == "Performance"
    assert fetched["frente_significado"]


# ---------------------------------------------------------------------------
# 2. Service: empty string / None clears the frente
# ---------------------------------------------------------------------------


def test_set_frente_with_empty_string_clears_it(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        set_frente(aluno["id"], "performance")

        set_frente(aluno["id"], "")

        fetched = get_aluno(aluno["id"])

    assert fetched is not None
    assert fetched["frente"] is None
    assert fetched["frente_label"] is None


def test_set_frente_with_none_clears_it(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        set_frente(aluno["id"], "longevidade")

        set_frente(aluno["id"], None)

        fetched = get_aluno(aluno["id"])

    assert fetched is not None
    assert fetched["frente"] is None
    assert fetched["frente_label"] is None


# ---------------------------------------------------------------------------
# 3. Service: switching frentes replaces the value
# ---------------------------------------------------------------------------


def test_set_frente_switches_from_one_option_to_another(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        set_frente(aluno["id"], "performance")

        set_frente(aluno["id"], "saude_integrada")

        fetched = get_aluno(aluno["id"])

    assert fetched is not None
    assert fetched["frente"] == "saude_integrada"
    assert fetched["frente_label"] == "Saúde Integrada"


# ---------------------------------------------------------------------------
# 4. Service: invalid frente raises ValidationError and persists nothing
# ---------------------------------------------------------------------------


def test_set_frente_with_invalid_value_raises_and_does_not_persist(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            set_frente(aluno["id"], "xpto")

        fetched = get_aluno(aluno["id"])

    assert fetched is not None
    assert fetched["frente"] is None


def test_set_frente_with_invalid_value_keeps_previous_frente(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        set_frente(aluno["id"], "longevidade")

        with pytest.raises(ValidationError):
            set_frente(aluno["id"], "xpto")

        fetched = get_aluno(aluno["id"])

    assert fetched is not None
    assert fetched["frente"] == "longevidade"


# ---------------------------------------------------------------------------
# 5. Service: non-existent aluno returns None
# ---------------------------------------------------------------------------


def test_set_frente_for_nonexistent_aluno_returns_none(data_dir: Path) -> None:
    with TestClient(app):
        result = set_frente(999999, "performance")

    assert result is None


# ---------------------------------------------------------------------------
# 6. Route: POST /alunos/{id}/frente -- success redirects and persists
# ---------------------------------------------------------------------------


def test_post_frente_route_with_valid_value_redirects_and_persists(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")

        response = client.post(
            f"/alunos/{aluno['id']}/frente",
            data={"frente": "performance"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/alunos/{aluno['id']}?atualizado=1"

        fetched = get_aluno(aluno["id"])

    assert fetched is not None
    assert fetched["frente"] == "performance"


# ---------------------------------------------------------------------------
# 7. Route: POST /alunos/{id}/frente -- non-existent aluno returns 404
# ---------------------------------------------------------------------------


def test_post_frente_route_for_nonexistent_aluno_returns_404(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos/999999/frente",
            data={"frente": "performance"},
            follow_redirects=False,
        )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 8. Route: POST /alunos/{id}/frente -- invalid value re-renders with 400
# ---------------------------------------------------------------------------


def test_post_frente_route_with_invalid_value_rerenders_with_400_and_saves_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")

        response = client.post(
            f"/alunos/{aluno['id']}/frente",
            data={"frente": "xpto"},
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert "location" not in response.headers

        fetched = get_aluno(aluno["id"])

    assert fetched is not None
    assert fetched["frente"] is None


# ---------------------------------------------------------------------------
# 9. Ficha: no frente shows "sem registro" and the select
# ---------------------------------------------------------------------------


def test_ficha_shows_sem_registro_and_select_when_no_frente(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    assert "sem registro" in response.text
    assert 'name="frente"' in response.text
    assert 'value="performance"' in response.text
    assert 'value="saude_integrada"' in response.text
    assert 'value="longevidade"' in response.text


# ---------------------------------------------------------------------------
# 10. Ficha: frente defined shows its label
# ---------------------------------------------------------------------------


def test_ficha_shows_frente_label_when_defined(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        set_frente(aluno["id"], "saude_integrada")

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    assert "Saúde Integrada" in response.text
