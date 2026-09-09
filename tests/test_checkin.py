"""Tests for the "checkin" (student daily check-in) domain -- Fase 2.

Covers the functional specification:

Service layer (``kairos.checkin.service``):
- ``registrar_checkin`` persists a check-in and ``checkin_de_hoje``/
  ``get_checkin`` return it back, with labels resolved
  (``sono_qualidade_label``, ``humor_label``);
- upsert semantics: registering twice for the same aluno+date does not
  create two rows -- the second call replaces the first, and
  ``checkin_de_hoje``/``list_checkins`` reflect the latest values only;
- validation: 0-10 scales (estresse/energia/dor_intensidade) reject values
  outside the range, ``sono_horas`` rejects values above 24, invalid
  ``sono_qualidade``/``humor`` options are rejected, and submitting every
  field empty raises a "preencha ao menos um campo" error -- in every
  invalid case nothing is persisted;
- ``list_checkins`` returns check-ins most-recent-date-first.

Student side (``/aluno/checkin``, session-scoped ``aluno_id``):
- ``GET /aluno/checkin`` renders 200 and pre-fills the form when a
  check-in for today already exists;
- ``POST /aluno/checkin`` with valid fields redirects (303) to ``/aluno``
  and persists under the session's aluno; an all-empty submission does not
  redirect (200, re-rendered) and persists nothing;
- isolation: the check-in is always scoped to the session's aluno_id, never
  to another aluno, regardless of what other students' data exists;
- the ``/aluno`` home shows a "Fazer check-in" call-to-action when there is
  no check-in for today, and a summary (with an "editar" link) once there
  is one.

Coach side (``/alunos/{id}/checkins``):
- renders 200 with the aluno's check-in history; 404 for a non-existent
  aluno.

Isolation: KAIROS_DATA_DIR points at a temp dir and the cached engine is
disposed on setup/teardown (same pattern as tests/test_area_aluno.py); the
suite-wide ``_no_remote_database_url`` autouse fixture (see
tests/conftest.py) already keeps KAIROS_DATABASE_URL out of the picture.
"""

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.checkin.service import (
    ValidationError,
    checkin_de_hoje,
    get_checkin,
    list_checkins,
    registrar_checkin,
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


def _login_as_aluno(monkeypatch: pytest.MonkeyPatch, aluno_id) -> None:
    """Override the suite-wide auto-login-as-coach patch with a student
    session for the current test.

    Patches the gate's own reference (``kairos.auth.middleware``), the
    student home route's directly-imported reference
    (``kairos.area_aluno.routes``), and the check-in routes' directly-
    imported reference (``kairos.checkin.routes``): each ``from ... import
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
    monkeypatch.setattr("kairos.checkin.routes.current_user", fake_current_user)


# ---------------------------------------------------------------------------
# 1. Service: registrar_checkin + checkin_de_hoje/get_checkin + labels
# ---------------------------------------------------------------------------


def test_registrar_checkin_persists_and_is_readable_back_with_labels(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        hoje = datetime.date.today()

        registrar_checkin(
            aluno["id"],
            hoje,
            sono_horas="7.5",
            sono_qualidade="boa",
            estresse=3,
            energia=8,
            humor="bom",
            dor_local="Joelho direito",
            dor_intensidade=2,
            observacao="Tudo bem hoje.",
        )

        de_hoje = checkin_de_hoje(aluno["id"])
        by_date = get_checkin(aluno["id"], hoje)

    assert de_hoje is not None
    assert by_date is not None
    assert de_hoje["id"] == by_date["id"]
    assert float(de_hoje["sono_horas"]) == 7.5
    assert de_hoje["sono_qualidade"] == "boa"
    assert de_hoje["sono_qualidade_label"] == "Boa"
    assert de_hoje["estresse"] == 3
    assert de_hoje["energia"] == 8
    assert de_hoje["humor"] == "bom"
    assert de_hoje["humor_label"] == "Bom"
    assert de_hoje["dor_local"] == "Joelho direito"
    assert de_hoje["dor_intensidade"] == 2
    assert de_hoje["observacao"] == "Tudo bem hoje."


# ---------------------------------------------------------------------------
# 2. Service: UPSERT (editable same day)
# ---------------------------------------------------------------------------


def test_registrar_checkin_twice_same_day_upserts_instead_of_duplicating(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        hoje = datetime.date.today()

        registrar_checkin(aluno["id"], hoje, energia=5)
        registrar_checkin(aluno["id"], hoje, energia=8)

        de_hoje = checkin_de_hoje(aluno["id"])
        historico = list_checkins(aluno["id"])

    assert de_hoje is not None
    assert de_hoje["energia"] == 8
    hoje_no_historico = [c for c in historico if c["data"] == hoje]
    assert len(hoje_no_historico) == 1
    assert hoje_no_historico[0]["energia"] == 8


# ---------------------------------------------------------------------------
# 3. Service: validations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("campo", ["estresse", "energia", "dor_intensidade"])
def test_registrar_checkin_rejects_scale_out_of_0_10_range(
    data_dir: Path, campo: str
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            registrar_checkin(
                aluno["id"], datetime.date.today(), **{campo: 11}
            )

        assert checkin_de_hoje(aluno["id"]) is None


@pytest.mark.parametrize("campo", ["estresse", "energia", "dor_intensidade"])
def test_registrar_checkin_rejects_negative_scale(
    data_dir: Path, campo: str
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            registrar_checkin(
                aluno["id"], datetime.date.today(), **{campo: -1}
            )

        assert checkin_de_hoje(aluno["id"]) is None


def test_registrar_checkin_rejects_sono_horas_above_24(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            registrar_checkin(aluno["id"], datetime.date.today(), sono_horas=25)

        assert checkin_de_hoje(aluno["id"]) is None


def test_registrar_checkin_rejects_invalid_sono_qualidade_option(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            registrar_checkin(
                aluno["id"], datetime.date.today(), sono_qualidade="excelente"
            )

        assert checkin_de_hoje(aluno["id"]) is None


def test_registrar_checkin_rejects_invalid_humor_option(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            registrar_checkin(
                aluno["id"], datetime.date.today(), humor="eufórico"
            )

        assert checkin_de_hoje(aluno["id"]) is None


def test_registrar_checkin_with_all_fields_empty_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError, match="Preencha ao menos um campo"):
            registrar_checkin(aluno["id"], datetime.date.today())

        assert checkin_de_hoje(aluno["id"]) is None
        assert list_checkins(aluno["id"]) == []


# ---------------------------------------------------------------------------
# 4. Service: list_checkins ordering (most recent date first)
# ---------------------------------------------------------------------------


def test_list_checkins_orders_by_date_descending(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        d1 = datetime.date(2026, 9, 1)
        d2 = datetime.date(2026, 9, 5)
        d3 = datetime.date(2026, 9, 3)

        registrar_checkin(aluno["id"], d1, energia=5)
        registrar_checkin(aluno["id"], d2, energia=6)
        registrar_checkin(aluno["id"], d3, energia=7)

        historico = list_checkins(aluno["id"])

    assert [c["data"] for c in historico] == [d2, d3, d1]


# ---------------------------------------------------------------------------
# 5. Student side: GET /aluno/checkin renders + pre-fills
# ---------------------------------------------------------------------------


def test_get_aluno_checkin_renders_form(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/checkin")

    assert response.status_code == 200
    assert "Check-in de hoje" in response.text


def test_get_aluno_checkin_prefills_form_when_already_registered_today(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        registrar_checkin(aluno["id"], datetime.date.today(), energia=8)
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/checkin")

    assert response.status_code == 200
    assert 'value="8"' in response.text


# ---------------------------------------------------------------------------
# 6. Student side: POST /aluno/checkin success and all-empty rejection
# ---------------------------------------------------------------------------


def test_post_aluno_checkin_with_valid_fields_redirects_and_persists(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/checkin",
            data={"energia": "9", "humor": "otimo"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/aluno"

        de_hoje = checkin_de_hoje(aluno["id"])

    assert de_hoje is not None
    assert de_hoje["energia"] == 9
    assert de_hoje["humor"] == "otimo"


def test_post_aluno_checkin_with_all_fields_empty_does_not_redirect_and_saves_nothing(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/checkin", data={}, follow_redirects=False
        )

    assert response.status_code != 303
    assert "location" not in response.headers
    assert checkin_de_hoje(aluno["id"]) is None


# ---------------------------------------------------------------------------
# 7. Student side: isolation (session's aluno_id only)
# ---------------------------------------------------------------------------


def test_post_aluno_checkin_always_writes_to_the_session_aluno_never_another(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        registrar_checkin(aluno_b["id"], datetime.date.today(), energia=2)

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.post(
            "/aluno/checkin", data={"energia": "7"}, follow_redirects=False
        )

        assert response.status_code == 303

        checkin_a = checkin_de_hoje(aluno_a["id"])
        checkins_b = list_checkins(aluno_b["id"])

    assert checkin_a is not None
    assert checkin_a["energia"] == 7
    assert len(checkins_b) == 1
    assert checkins_b[0]["energia"] == 2  # unchanged by aluno A's POST


# ---------------------------------------------------------------------------
# 8. Home: CTA vs summary card
# ---------------------------------------------------------------------------


def test_aluno_home_shows_checkin_cta_when_no_checkin_today(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Fazer check-in" in response.text


def test_aluno_home_shows_checkin_summary_and_edit_link_when_registered_today(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        registrar_checkin(aluno["id"], datetime.date.today(), humor="bom")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Humor:" in response.text
    assert "editar" in response.text
    assert "Fazer check-in" not in response.text


# ---------------------------------------------------------------------------
# 9. Coach side: GET /alunos/{id}/checkins
# ---------------------------------------------------------------------------


def test_get_coach_checkins_lists_alunos_history(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        registrar_checkin(
            aluno["id"], datetime.date(2026, 9, 1), energia=6, humor="neutro"
        )

        response = client.get(f"/alunos/{aluno['id']}/checkins")

    assert response.status_code == 200
    assert "01/09/2026" in response.text
    assert "Neutro" in response.text


def test_get_coach_checkins_for_nonexistent_aluno_returns_404(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999999/checkins")

    assert response.status_code == 404
