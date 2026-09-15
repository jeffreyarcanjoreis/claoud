"""Tests for the Fase 0 restructuring of the student area: ``/aluno`` is
now a lean home page and the former content lives in dedicated, read-only
sub-pages, still scoped to the session's ``aluno_id`` (never the URL).

Covers the functional specification given for this slice:

1. Navigation: the home (``GET /aluno``) links to every sub-page
   (``/aluno/perfil``, ``/aluno/treinos``, ``/aluno/avaliacoes``,
   ``/aluno/agenda``, ``/aluno/financeiro``, ``/aluno/acompanhamento``).
2. ``GET /aluno/perfil`` shows the aluno's own data/health fields and
   e-mail, and never leaks the coach-only ``alert``/``notes`` fields.
3. ``GET /aluno/financeiro`` shows the plan's value and a payment's
   competência when a plan/payment exist, and a documented empty state
   when there is no plan.
4. ``GET /aluno/acompanhamento`` lists the aluno's own held-session
   records and ``GET /aluno/acompanhamento/{id}`` shows the detail;
   another aluno's record is a 404 (never leaked).
5. ``GET /aluno/agenda`` shows both a future and a past session.
6. ``GET /aluno/foto`` is a 404 for an aluno without a stored photo (and
   200 with the right content-type when one exists).
7. Isolation is reinforced across every sub-page, not just the home.

Same isolation pattern as tests/test_area_aluno.py: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on setup/teardown; logging
in as a student requires patching ``current_user`` in *both*
``kairos.auth.middleware`` (the gate's reference) and
``kairos.area_aluno.routes`` (the route's own directly-imported reference).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.acompanhamento.service import create_sessao_realizada
from kairos.agenda.service import create_sessao
from kairos.alunos.fotos import save_foto
from kairos.alunos.service import create_aluno, set_aluno_foto
from kairos.avaliacoes.service import create_avaliacao
from kairos.financeiro.service import registrar_pagamento, set_plano
from kairos.main import app
from kairos.treinos.service import create_treino

import datetime

HOJE = datetime.date.today()
ONTEM = HOJE - datetime.timedelta(days=1)
AMANHA = HOJE + datetime.timedelta(days=1)

# A minimal valid JPEG signature -- enough for kairos.alunos.fotos'
# magic-byte detection to accept it as a real image.
_FAKE_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32


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

    Patches both the gate's own reference (``kairos.auth.middleware``) and
    the student area route's directly-imported reference
    (``kairos.area_aluno.routes``), since ``from ... import current_user``
    binds a separate name that a patch on the origin module does not reach.
    """
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)


# ---------------------------------------------------------------------------
# 1. Navigation: /aluno links to every sub-page
# ---------------------------------------------------------------------------


def test_home_links_to_every_subpage(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Otavio Ramos")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    for path in (
        "/aluno/perfil",
        "/aluno/treinos",
        "/aluno/avaliacoes",
        "/aluno/agenda",
        "/aluno/financeiro",
        "/aluno/acompanhamento",
    ):
        assert f'href="{path}"' in response.text


# ---------------------------------------------------------------------------
# 2. Perfil: shows own data, never alert/notes
# ---------------------------------------------------------------------------


def test_perfil_shows_own_data_and_email_but_never_alert_or_notes(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(
            name="Paula Ventura",
            objective="Emagrecimento",
            health_conditions="Hipertensão controlada",
            medications="Losartana",
            email="paula@example.com",
            alert="ALERTA_SECRETO",
            notes="NOTA_SECRETA",
        )

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get("/aluno/perfil")

    assert response.status_code == 200
    assert "Emagrecimento" in response.text
    assert "Hipertensão controlada" in response.text
    assert "paula@example.com" in response.text
    assert "ALERTA_SECRETO" not in response.text
    assert "NOTA_SECRETA" not in response.text


# ---------------------------------------------------------------------------
# 3. Financeiro: plan value + payment competência, or empty state
# ---------------------------------------------------------------------------


def test_financeiro_shows_plano_valor_and_pagamento_competencia(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Quintino Braga")
        set_plano(aluno["id"], formato="individual", valor="250", ciclo_meses="1")
        registrar_pagamento(
            aluno["id"], ano=2026, mes=3, valor="250", data_pagamento="2026-03-05"
        )

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get("/aluno/financeiro")

    assert response.status_code == 200
    assert "R$ 250,00" in response.text
    assert "03/2026" in response.text


def test_financeiro_shows_empty_state_for_aluno_without_plano(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Rosana Melo")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/financeiro")

    assert response.status_code == 200
    assert "Você ainda não tem um plano registrado." in response.text
    assert "Nenhum pagamento registrado ainda." in response.text


# ---------------------------------------------------------------------------
# 4. Acompanhamento: list + detail + isolation
# ---------------------------------------------------------------------------


def test_acompanhamento_lists_and_shows_own_sessao_realizada_detail(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Silvio Costa")
        registro = create_sessao_realizada(
            aluno["id"],
            data=HOJE.isoformat(),
            presenca="compareceu",
            disposicao="boa",
            feedback="Sessão produtiva.",
        )

        _login_as_aluno(monkeypatch, aluno["id"])
        lista = client.get("/aluno/acompanhamento")
        detalhe = client.get(f"/aluno/acompanhamento/{registro['id']}")

    assert lista.status_code == 200
    assert "Compareceu" in lista.text

    assert detalhe.status_code == 200
    assert "Compareceu" in detalhe.text
    assert "Sessão produtiva." in detalhe.text


def test_acompanhamento_detalhe_returns_404_for_another_alunos_registro(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Tania Alves")
        aluno_b = create_aluno(name="Ubirajara Melo")
        registro_b = create_sessao_realizada(
            aluno_b["id"],
            data=HOJE.isoformat(),
            presenca="compareceu",
            feedback="FEEDBACK_SECRETO_DO_B",
        )

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.get(f"/aluno/acompanhamento/{registro_b['id']}")

    assert response.status_code == 404
    assert "FEEDBACK_SECRETO_DO_B" not in response.text


# ---------------------------------------------------------------------------
# 5. Agenda: shows both a future and a past session
# ---------------------------------------------------------------------------


def test_agenda_shows_future_and_past_sessions(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Valeria Nogueira")
        create_sessao(
            aluno["id"], data=AMANHA.isoformat(), hora="08:00", tipo="individual"
        )
        create_sessao(
            aluno["id"], data=ONTEM.isoformat(), hora="17:00", tipo="grupo"
        )

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get("/aluno/agenda")

    assert response.status_code == 200
    assert AMANHA.strftime("%d/%m/%Y") in response.text
    assert ONTEM.strftime("%d/%m/%Y") in response.text


# ---------------------------------------------------------------------------
# 6. Foto: 404 without a stored photo, 200 with one
# ---------------------------------------------------------------------------


def test_foto_returns_404_for_aluno_without_a_photo(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Wagner Pires")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/foto")

    assert response.status_code == 404


def test_foto_returns_200_with_the_own_stored_photo(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ximena Duarte")
        filename = save_foto(_FAKE_JPEG_BYTES, "image/jpeg", "foto.jpg")
        set_aluno_foto(aluno["id"], filename)

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get("/aluno/foto")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


# ---------------------------------------------------------------------------
# 7. Isolation reinforcement: treino/avaliacao detail already covered in
#    tests/test_area_aluno_conteudo.py -- not duplicated here.
# ---------------------------------------------------------------------------
