"""Tests for issue 26 (Fase 3.2 / Fase 0 restructuring): the student area
shows the logged-in student's own content, read-only and isolated from
every other student.

Since the Fase 0 restructuring, ``GET /aluno`` is a lean home (greeting +
next session + static shortcut links) and the former lists each moved to
their own sub-page. Covers the functional specification of
``kairos/area_aluno/routes.py``:

- ``GET /aluno/treinos`` lists the session's own workouts
  (``list_treinos``); ``GET /aluno/avaliacoes`` lists the session's own
  assessments (``list_avaliacoes``) -- another student's data never
  appears on either page;
- ``GET /aluno/agenda`` lists upcoming sessions ("Próximas sessões", only
  ``data >= hoje``) and past sessions ("Histórico", ``data < hoje``), both
  from ``list_sessoes`` and scoped to the session's ``aluno_id``;
- ``GET /aluno/acompanhamento`` lists the session's own held-session
  records (``list_sessoes_realizadas``);
- a student with no data yet sees the documented empty-state messages on
  each sub-page instead of a crash;
- ``GET /aluno/treinos/{treino_id}`` renders the workout read-only when it
  belongs to the session's aluno; 404 (never another aluno's data) when the
  workout belongs to someone else or does not exist at all;
- ``GET /aluno/avaliacoes/{avaliacao_id}`` follows the same ownership rule;
- when the session's ``aluno_id`` does not resolve to any Aluno, ``GET
  /aluno`` and every sub-page still render (200) with empty sections
  instead of crashing;
- the area is read-only: there is no POST route under ``/aluno`` for content
  (workouts/assessments), so a POST is rejected (405/404), never treated as
  a write that succeeds with 200.

Same isolation pattern as tests/test_area_aluno.py (Fase 3.1): KAIROS_DATA_DIR
points at a temp dir and the cached engine is disposed on setup/teardown, and
logging in as a student requires patching ``current_user`` in *both*
``kairos.auth.middleware`` (the gate's reference) and
``kairos.area_aluno.routes`` (the route's own directly-imported reference).
"""

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.acompanhamento.service import create_sessao_realizada
from kairos.agenda.service import create_sessao
from kairos.alunos.service import create_aluno
from kairos.avaliacoes.service import create_avaliacao
from kairos.main import app
from kairos.treinos.service import create_treino

HOJE = datetime.date.today()
ONTEM = HOJE - datetime.timedelta(days=1)
AMANHA = HOJE + datetime.timedelta(days=1)


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
    the student landing route's directly-imported reference
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
# 1. Treinos/avaliacoes sub-pages show only the logged-in aluno's own data
# ---------------------------------------------------------------------------


def test_treinos_page_shows_own_but_not_another_alunos_workout(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Ana Costa")
        aluno_b = create_aluno(name="Bruno Duarte")

        create_treino(aluno_a["id"], nome="Treino da Ana")
        create_treino(aluno_b["id"], nome="Treino do Bruno")

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.get("/aluno/treinos")

    assert response.status_code == 200
    assert "Treino da Ana" in response.text
    assert "Treino do Bruno" not in response.text


def test_avaliacoes_page_shows_own_but_not_another_alunos_assessment(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Ana Costa")
        aluno_b = create_aluno(name="Bruno Duarte")

        create_avaliacao(aluno_a["id"], data=HOJE.isoformat(), peso="60")
        create_avaliacao(aluno_b["id"], data=(HOJE - datetime.timedelta(days=5)).isoformat(), peso="80")

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.get("/aluno/avaliacoes")

    assert response.status_code == 200
    assert HOJE.strftime("%d/%m/%Y") in response.text
    assert (HOJE - datetime.timedelta(days=5)).strftime("%d/%m/%Y") not in response.text


# ---------------------------------------------------------------------------
# 2. /aluno/agenda splits sessions into upcoming ("Próximas sessões") and
#    past ("Histórico")
# ---------------------------------------------------------------------------


def test_agenda_page_lists_future_session_under_proximas_and_past_under_historico(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Carla Nunes")
        create_sessao(
            aluno["id"], data=ONTEM.isoformat(), hora="10:00", tipo="individual"
        )
        create_sessao(
            aluno["id"], data=AMANHA.isoformat(), hora="09:00", tipo="individual"
        )

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get("/aluno/agenda")

    assert response.status_code == 200
    proximas_text, historico_text = response.text.split("Histórico", 1)

    # The future session is listed under "Próximas sessões" (before the
    # "Histórico" heading) and the past session under "Histórico" (after
    # it) -- neither the empty-state messages apply since both are present.
    assert AMANHA.strftime("%d/%m/%Y") in proximas_text
    assert ONTEM.strftime("%d/%m/%Y") not in proximas_text
    assert ONTEM.strftime("%d/%m/%Y") in historico_text
    assert "Nenhuma sessão próxima." not in response.text
    assert "Sem sessões anteriores." not in response.text


def test_home_landing_still_shows_the_next_upcoming_session(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The home (``/aluno``) keeps showing only the single next session --
    it no longer lists the full agenda (that moved to ``/aluno/agenda``)."""
    with TestClient(app) as client:
        aluno = create_aluno(name="Carla Nunes")
        create_sessao(
            aluno["id"], data=ONTEM.isoformat(), hora="10:00", tipo="individual"
        )
        create_sessao(
            aluno["id"], data=AMANHA.isoformat(), hora="09:00", tipo="individual"
        )

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get("/aluno")

    assert response.status_code == 200
    assert AMANHA.strftime("%d/%m/%Y") in response.text
    assert ONTEM.strftime("%d/%m/%Y") not in response.text
    assert "Nenhuma sessão agendada." not in response.text


# ---------------------------------------------------------------------------
# 3. Empty states (each on its own sub-page, since the Fase 0 restructuring)
# ---------------------------------------------------------------------------


def test_empty_state_messages_for_aluno_with_no_data_on_each_subpage(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Diego Prado")
        _login_as_aluno(monkeypatch, aluno["id"])

        home = client.get("/aluno")
        treinos_page = client.get("/aluno/treinos")
        avaliacoes_page = client.get("/aluno/avaliacoes")
        agenda_page = client.get("/aluno/agenda")
        acompanhamento_page = client.get("/aluno/acompanhamento")

    assert home.status_code == 200
    assert "Nenhuma sessão agendada." in home.text

    assert treinos_page.status_code == 200
    assert "Nenhum treino atribuído ainda." in treinos_page.text

    assert avaliacoes_page.status_code == 200
    assert "Nenhuma avaliação registrada ainda." in avaliacoes_page.text

    assert agenda_page.status_code == 200
    assert "Nenhuma sessão próxima." in agenda_page.text
    assert "Sem sessões anteriores." in agenda_page.text

    assert acompanhamento_page.status_code == 200
    assert "Sem sessões registradas ainda." in acompanhamento_page.text


# ---------------------------------------------------------------------------
# 4-6. Treino detail: owner / not-owner / non-existent
# ---------------------------------------------------------------------------


def test_treino_detalhe_renders_for_the_owner(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Elisa Matos")
        treino = create_treino(aluno["id"], nome="Treino de Elisa")

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 200
    assert "Treino de Elisa" in response.text


def test_treino_detalhe_returns_404_for_another_alunos_workout(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Fabio Alves")
        aluno_b = create_aluno(name="Gustavo Reis")
        treino_b = create_treino(aluno_b["id"], nome="Treino Secreto do Gustavo")

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.get(f"/aluno/treinos/{treino_b['id']}")

    assert response.status_code == 404
    assert "Treino Secreto do Gustavo" not in response.text


def test_treino_detalhe_returns_404_for_nonexistent_id(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Helena Souza")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/treinos/999999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 7. Avaliacao detail: owner / not-owner / non-existent
# ---------------------------------------------------------------------------


def test_avaliacao_detalhe_renders_for_the_owner(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Igor Peixoto")
        avaliacao = create_avaliacao(
            aluno["id"], data=HOJE.isoformat(), peso="70"
        )

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/avaliacoes/{avaliacao['id']}")

    assert response.status_code == 200
    assert HOJE.strftime("%d/%m/%Y") in response.text


def test_avaliacao_detalhe_returns_404_for_another_alunos_assessment(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Julia Farias")
        aluno_b = create_aluno(name="Karina Lopes")
        avaliacao_b = create_avaliacao(
            aluno_b["id"], data=HOJE.isoformat(), peso="55"
        )

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.get(f"/aluno/avaliacoes/{avaliacao_b['id']}")

    assert response.status_code == 404


def test_avaliacao_detalhe_returns_404_for_nonexistent_id(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Luana Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/avaliacoes/999999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 8. Session's aluno_id does not resolve to any Aluno
# ---------------------------------------------------------------------------


def test_landing_does_not_crash_when_session_aluno_id_is_unresolvable(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _login_as_aluno(monkeypatch, 424242)  # no Aluno with this id

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Olá!" in response.text
    assert "Nenhuma sessão agendada." in response.text


def test_every_subpage_does_not_crash_when_session_aluno_id_is_unresolvable(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _login_as_aluno(monkeypatch, 424242)  # no Aluno with this id

        treinos_page = client.get("/aluno/treinos")
        avaliacoes_page = client.get("/aluno/avaliacoes")
        agenda_page = client.get("/aluno/agenda")
        acompanhamento_page = client.get("/aluno/acompanhamento")
        perfil_page = client.get("/aluno/perfil")
        financeiro_page = client.get("/aluno/financeiro")
        foto_page = client.get("/aluno/foto")

    assert treinos_page.status_code == 200
    assert "Nenhum treino atribuído ainda." in treinos_page.text

    assert avaliacoes_page.status_code == 200
    assert "Nenhuma avaliação registrada ainda." in avaliacoes_page.text

    assert agenda_page.status_code == 200
    assert "Nenhuma sessão próxima." in agenda_page.text
    assert "Sem sessões anteriores." in agenda_page.text

    assert acompanhamento_page.status_code == 200
    assert "Sem sessões registradas ainda." in acompanhamento_page.text

    assert perfil_page.status_code == 200
    assert "Não encontramos os seus dados de perfil." in perfil_page.text

    assert financeiro_page.status_code == 200
    assert "Você ainda não tem um plano registrado." in financeiro_page.text
    assert "Nenhum pagamento registrado ainda." in financeiro_page.text

    assert foto_page.status_code == 404


# ---------------------------------------------------------------------------
# 9. Read-only: no write route under /aluno
# ---------------------------------------------------------------------------


def test_post_to_treino_detail_url_is_not_a_successful_write(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcelo Tanaka")
        treino = create_treino(aluno["id"], nome="Treino de Marcelo")

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(f"/aluno/treinos/{treino['id']}")

    assert response.status_code in (404, 405)


def test_post_to_aluno_landing_url_is_not_a_successful_write(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Nina Barros")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post("/aluno")

    assert response.status_code in (404, 405)
