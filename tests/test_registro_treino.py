"""Tests for the "registro_treino" (student post-workout log) domain --
Fase 3.

Covers the functional specification:

Service layer (``kairos.registro_treino.service``):
- ``registrar`` persists a post-workout log and ``list_registros`` returns
  it back, most-recent-date-first, with ``sensacao_label`` resolved and
  ``treino_nome`` filled in via a join when a ``treino_id`` was given;
- validation: ``rpe`` outside the 0-10 range is rejected, an invalid
  ``sensacao`` option is rejected, a ``treino_id`` that belongs to another
  student is rejected ("Treino inválido."), and submitting every content
  field empty raises a "preencha ao menos um campo" error -- in every
  invalid case nothing is persisted;
- an empty/``None`` ``treino_id`` is accepted (no workout link) as long as
  some other content field is filled in.

Student side (``/aluno/registro``, session-scoped ``aluno_id``):
- ``GET /aluno/registro`` renders 200 with the form and the "Meus
  registros" history section;
- ``POST /aluno/registro`` with valid fields redirects (303) to
  ``/aluno/registro`` and persists under the session's aluno; an all-empty
  submission does not redirect (200, re-rendered) and persists nothing;
- isolation: the log is always scoped to the session's aluno_id, never to
  another aluno's, and a ``treino_id`` belonging to another aluno is
  rejected rather than silently accepted;
- the ``/aluno`` home shows a "Registrar" call-to-action when there is a
  workout session today and no log for today yet; the CTA disappears once
  today's log has been made, and does not appear at all when there is no
  workout session today.

Coach side (``/alunos/{id}/acompanhamento``):
- the "Registros do aluno" section appears with the student's post-workout
  logs; a non-existent aluno still returns 404 (existing behaviour).

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
    SENSACAO_LABELS,
    ValidationError,
    get_registro,
    list_registros,
    registrar,
)
from kairos.main import app
from kairos.treinos.service import create_treino


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
    monkeypatch.setattr(
        "kairos.registro_treino.routes.current_user", fake_current_user
    )


# ---------------------------------------------------------------------------
# 1. Service: registrar + list_registros (labels, treino_nome, ordering)
# ---------------------------------------------------------------------------


def test_registrar_persists_and_list_registros_returns_it_with_labels(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        treino = create_treino(aluno["id"], nome="Treino A")
        hoje = datetime.date.today()

        registrar(
            aluno["id"],
            data=hoje,
            treino_id=treino["id"],
            rpe=7,
            sensacao="boa",
            o_que_mudou="Mais disposição.",
            dor_nova="Nenhuma.",
        )

        registros = list_registros(aluno["id"])

    assert len(registros) == 1
    r = registros[0]
    assert r["aluno_id"] == aluno["id"]
    assert r["data"] == hoje
    assert r["treino_id"] == treino["id"]
    assert r["treino_nome"] == "Treino A"
    assert r["rpe"] == 7
    assert r["sensacao"] == "boa"
    assert r["sensacao_label"] == SENSACAO_LABELS["boa"] == "Boa"
    assert r["o_que_mudou"] == "Mais disposição."
    assert r["dor_nova"] == "Nenhuma."


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


def test_get_registro_returns_treino_nome_via_join(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        treino = create_treino(aluno["id"], nome="Treino B")

        created = registrar(aluno["id"], treino_id=treino["id"], rpe=4)
        fetched = get_registro(created["id"])

    assert fetched is not None
    assert fetched["treino_nome"] == "Treino B"


# ---------------------------------------------------------------------------
# 2. Service: validations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valor", [-1, 11])
def test_registrar_rejects_rpe_out_of_0_10_range(
    data_dir: Path, valor: int
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            registrar(aluno["id"], rpe=valor)

        assert list_registros(aluno["id"]) == []


def test_registrar_rejects_invalid_sensacao_option(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            registrar(aluno["id"], sensacao="excelente")

        assert list_registros(aluno["id"]) == []


def test_registrar_rejects_treino_id_belonging_to_another_aluno(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        treino_b = create_treino(aluno_b["id"], nome="Treino do B")

        with pytest.raises(ValidationError, match="Treino inválido."):
            registrar(aluno_a["id"], treino_id=treino_b["id"], rpe=5)

        assert list_registros(aluno_a["id"]) == []


def test_registrar_with_all_content_fields_empty_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(
            ValidationError, match="Preencha ao menos um campo"
        ):
            registrar(aluno["id"])

        assert list_registros(aluno["id"]) == []


# ---------------------------------------------------------------------------
# 3. Service: empty/None treino_id means no workout link
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("treino_id", [None, "", "   "])
def test_registrar_with_empty_treino_id_creates_registro_without_workout_link(
    data_dir: Path, treino_id
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        registrar(aluno["id"], treino_id=treino_id, rpe=6)

        registros = list_registros(aluno["id"])

    assert len(registros) == 1
    assert registros[0]["treino_id"] is None
    assert registros[0]["treino_nome"] is None


# ---------------------------------------------------------------------------
# 4. Student side: GET /aluno/registro
# ---------------------------------------------------------------------------


def test_get_aluno_registro_renders_form_and_history_section(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/registro")

    assert response.status_code == 200
    assert "Meus registros" in response.text


# ---------------------------------------------------------------------------
# 5. Student side: POST /aluno/registro success and all-empty rejection
# ---------------------------------------------------------------------------


def test_post_aluno_registro_with_valid_fields_redirects_and_persists(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/registro",
            data={"rpe": "8", "sensacao": "otima"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/aluno/registro"

        registros = list_registros(aluno["id"])

    assert len(registros) == 1
    assert registros[0]["rpe"] == 8
    assert registros[0]["sensacao"] == "otima"


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
# 6. Student side: isolation (session's aluno_id only)
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


def test_post_aluno_registro_with_another_alunos_treino_id_is_rejected(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        treino_b = create_treino(aluno_b["id"], nome="Treino do B")

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.post(
            "/aluno/registro",
            data={"treino_id": str(treino_b["id"]), "rpe": "5"},
            follow_redirects=False,
        )

        registros_a = list_registros(aluno_a["id"])

    assert response.status_code != 303
    assert "location" not in response.headers
    assert registros_a == []


# ---------------------------------------------------------------------------
# 7. Home: CTA appears/disappears based on today's workout session and log
# ---------------------------------------------------------------------------


def test_aluno_home_shows_registrar_cta_when_workout_today_and_no_log_yet(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        hoje = datetime.date.today()
        create_sessao(
            aluno["id"], data=hoje.isoformat(), hora="10:00", tipo="individual"
        )
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Registrar" in response.text


def test_aluno_home_hides_registrar_cta_after_logging_today(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        hoje = datetime.date.today()
        create_sessao(
            aluno["id"], data=hoje.isoformat(), hora="10:00", tipo="individual"
        )
        registrar(aluno["id"], data=hoje, rpe=5)
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Registrar" not in response.text


def test_aluno_home_hides_registrar_cta_when_no_workout_session_today(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Registrar" not in response.text


# ---------------------------------------------------------------------------
# 8. Coach side: GET /alunos/{id}/acompanhamento
# ---------------------------------------------------------------------------


def test_get_coach_acompanhamento_shows_registros_do_aluno_section(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        registrar(aluno["id"], o_que_mudou="Correu 5km sem dor.")

        response = client.get(f"/alunos/{aluno['id']}/acompanhamento")

    assert response.status_code == 200
    assert "Registros do aluno" in response.text
    assert "Correu 5km sem dor." in response.text


def test_get_coach_acompanhamento_for_nonexistent_aluno_returns_404(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999999/acompanhamento")

    assert response.status_code == 404
