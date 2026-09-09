"""Tests for the "registro_treino" (student post-workout log) domain --
issue 37.

Covers the functional specification:

Service layer (``kairos.registro_treino.service``):
- ``registrar`` persists a new post-workout log entry and
  ``list_registros``/``get_registro`` return it back, with
  ``sensacao_label`` and ``treino_nome`` resolved;
- unlike checkin, this is never an upsert: registering twice for the same
  aluno+date creates two separate rows;
- validation: RPE outside 0-10 is rejected, an invalid ``sensacao`` option
  is rejected, submitting every content field empty raises a "preencha ao
  menos um campo" error, and a ``treino_id`` belonging to another aluno is
  rejected -- in every invalid case nothing is persisted;
- ``list_registros`` returns entries most-recent-date-first.

Student side (``/aluno/registro``, session-scoped ``aluno_id``):
- ``GET /aluno/registro`` renders 200 with the "Como foi o treino?" form
  and the student's own history;
- ``POST /aluno/registro`` with valid fields redirects (303) to
  ``/aluno/registro`` and persists under the session's aluno; an all-empty
  submission does not redirect and persists nothing;
- isolation: the log entry is always scoped to the session's aluno_id,
  never to another aluno.

Coach side (``/alunos/{id}/acompanhamento``):
- the "Registros do aluno" section renders the aluno's post-workout log
  history; 404 for a non-existent aluno (pre-existing behavior).

Isolation: KAIROS_DATA_DIR points at a temp dir and the cached engine is
disposed on setup/teardown (same pattern as tests/test_checkin.py); the
suite-wide ``_no_remote_database_url`` autouse fixture (see
tests/conftest.py) already keeps KAIROS_DATABASE_URL out of the picture.
"""

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.agenda.service import create_sessao
from kairos.alunos.service import create_aluno
from kairos.registro_treino.service import (
    ValidationError,
    get_registro,
    list_registros,
    registrar,
)
from kairos.treinos.service import create_treino
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
    (``kairos.area_aluno.routes``), and the registro_treino routes'
    directly-imported reference (``kairos.registro_treino.routes``): each
    ``from ... import current_user`` binds a separate name that a patch on
    the origin module does not reach.
    """
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)
    monkeypatch.setattr("kairos.registro_treino.routes.current_user", fake_current_user)


# ---------------------------------------------------------------------------
# 1. Service: registrar + list_registros/get_registro + labels/treino_nome
# ---------------------------------------------------------------------------


def test_registrar_persists_and_is_readable_back_with_labels(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        treino = create_treino(aluno["id"], nome="Treino A")

        criado = registrar(
            aluno["id"],
            treino_id=treino["id"],
            rpe=7,
            sensacao="boa",
            o_que_mudou="Aumentei a carga do supino.",
            dor_nova="Leve dor no ombro.",
        )

        registros = list_registros(aluno["id"])
        by_id = get_registro(criado["id"])

    assert len(registros) == 1
    assert by_id is not None
    assert by_id["id"] == criado["id"]
    assert by_id["aluno_id"] == aluno["id"]
    assert by_id["treino_id"] == treino["id"]
    assert by_id["treino_nome"] == "Treino A"
    assert by_id["rpe"] == 7
    assert by_id["sensacao"] == "boa"
    assert by_id["sensacao_label"] == "Boa"
    assert by_id["o_que_mudou"] == "Aumentei a carga do supino."
    assert by_id["dor_nova"] == "Leve dor no ombro."
    assert by_id["data"] == datetime.date.today()


# ---------------------------------------------------------------------------
# 2. Service: NOT an upsert -- multiple entries per aluno/day are allowed
# ---------------------------------------------------------------------------


def test_registrar_twice_same_day_creates_two_separate_entries(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        hoje = datetime.date.today()

        registrar(aluno["id"], data=hoje, rpe=5)
        registrar(aluno["id"], data=hoje, rpe=8)

        registros = list_registros(aluno["id"])

    assert len(registros) == 2
    assert {r["rpe"] for r in registros} == {5, 8}
    assert all(r["data"] == hoje for r in registros)


# ---------------------------------------------------------------------------
# 3. Service: validations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rpe_invalido", [11, -1])
def test_registrar_rejects_rpe_out_of_0_10_range(
    data_dir: Path, rpe_invalido: int
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError, match="RPE deve ser de 0 a 10"):
            registrar(aluno["id"], rpe=rpe_invalido)

        assert list_registros(aluno["id"]) == []


def test_registrar_rejects_invalid_sensacao_option(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError, match="Sensação inválida"):
            registrar(aluno["id"], sensacao="excelente")

        assert list_registros(aluno["id"]) == []


def test_registrar_with_all_content_fields_empty_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError, match="Preencha ao menos um campo"):
            registrar(aluno["id"])

        assert list_registros(aluno["id"]) == []


def test_registrar_rejects_treino_id_belonging_to_another_aluno(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        treino_de_b = create_treino(aluno_b["id"], nome="Treino de B")

        with pytest.raises(ValidationError, match="Treino inválido"):
            registrar(aluno_a["id"], treino_id=treino_de_b["id"], rpe=5)

        assert list_registros(aluno_a["id"]) == []


# ---------------------------------------------------------------------------
# 4. Service: list_registros ordering (most recent date first)
# ---------------------------------------------------------------------------


def test_list_registros_orders_by_date_descending(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        d1 = datetime.date(2026, 9, 1)
        d2 = datetime.date(2026, 9, 5)
        d3 = datetime.date(2026, 9, 3)

        registrar(aluno["id"], data=d1, rpe=5)
        registrar(aluno["id"], data=d2, rpe=6)
        registrar(aluno["id"], data=d3, rpe=7)

        registros = list_registros(aluno["id"])

    assert [r["data"] for r in registros] == [d2, d3, d1]


# ---------------------------------------------------------------------------
# 5. Student side: GET /aluno/registro renders
# ---------------------------------------------------------------------------


def test_get_aluno_registro_renders_form(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/registro")

    assert response.status_code == 200
    assert "Como foi o treino?" in response.text


# ---------------------------------------------------------------------------
# 6. Student side: POST /aluno/registro success and all-empty rejection
# ---------------------------------------------------------------------------


def test_post_aluno_registro_with_valid_fields_redirects_and_persists(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/registro",
            data={"rpe": "6", "sensacao": "boa"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/aluno/registro"

        registros = list_registros(aluno["id"])

    assert len(registros) == 1
    assert registros[0]["rpe"] == 6
    assert registros[0]["sensacao"] == "boa"


def test_post_aluno_registro_with_all_fields_empty_does_not_redirect_and_saves_nothing(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/registro", data={}, follow_redirects=False
        )

    assert response.status_code != 303
    assert "location" not in response.headers
    assert list_registros(aluno["id"]) == []


# ---------------------------------------------------------------------------
# 7. Student side: isolation (session's aluno_id only)
# ---------------------------------------------------------------------------


def test_post_aluno_registro_always_writes_to_the_session_aluno_never_another(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        registrar(aluno_b["id"], rpe=2)

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.post(
            "/aluno/registro", data={"rpe": "9"}, follow_redirects=False
        )

        assert response.status_code == 303

        registros_a = list_registros(aluno_a["id"])
        registros_b = list_registros(aluno_b["id"])

    assert len(registros_a) == 1
    assert registros_a[0]["rpe"] == 9
    assert len(registros_b) == 1
    assert registros_b[0]["rpe"] == 2  # unchanged by aluno A's POST


# ---------------------------------------------------------------------------
# 8. Coach side: GET /alunos/{id}/acompanhamento shows the aluno's log
# ---------------------------------------------------------------------------


def test_get_coach_acompanhamento_lists_alunos_registros_treino(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        registrar(
            aluno["id"],
            data=datetime.date(2026, 9, 1),
            rpe=8,
            sensacao="otima",
        )

        response = client.get(f"/alunos/{aluno['id']}/acompanhamento")

    assert response.status_code == 200
    assert "Registros do aluno" in response.text
    assert "01/09/2026" in response.text
    assert "Ótima" in response.text


def test_get_coach_acompanhamento_for_nonexistent_aluno_returns_404(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999999/acompanhamento")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 9. Home: CTA "Como foi o treino de hoje? Registrar"
# ---------------------------------------------------------------------------


def test_aluno_home_shows_registro_cta_when_session_today_and_no_registro_yet(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        hoje = datetime.date.today()
        create_sessao(
            aluno["id"],
            data=hoje.isoformat(),
            hora="18:00",
            tipo="individual",
        )
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Como foi o treino de hoje? Registrar" in response.text


def test_aluno_home_hides_registro_cta_when_no_session_today(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Como foi o treino de hoje? Registrar" not in response.text


def test_aluno_home_hides_registro_cta_when_session_today_but_already_registered(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        hoje = datetime.date.today()
        create_sessao(
            aluno["id"],
            data=hoje.isoformat(),
            hora="18:00",
            tipo="individual",
        )
        registrar(aluno["id"], data=hoje, rpe=5)
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Como foi o treino de hoje? Registrar" not in response.text
