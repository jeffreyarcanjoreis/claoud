"""Tests for issue 35 (Fase 1): the student <-> coach messaging channel.

Covers the functional specification:

- Service layer (``kairos.mensagens.service``): ``enviar_mensagem`` persists
  and validates (``autor`` in {coach, aluno}, non-empty ``texto``);
  ``listar_conversa`` returns the full conversation in chronological order;
  ``marcar_lidas``/``contar_nao_lidas`` model "lida" as "the recipient (the
  *other* side) has read it"; ``ultima_do_coach`` returns the most recent
  coach message or None; ``alunos_com_nao_lidas`` maps aluno_id to how many
  of that aluno's own messages are still unread by the coach.
- The student's own side (``/aluno/mensagens``): always scoped to the
  session's ``aluno_id`` (never the URL); GET marks the coach's messages as
  read; POST appends as ``autor="aluno"`` and redirects (303); an empty
  ``texto`` re-renders with an error and persists nothing.
- The student's home (``/aluno``): a "Recado do coach" card shows the
  latest coach message (with an unread badge) when one exists, and is
  absent otherwise.
- The coach's side (``/alunos/{id}/mensagens``): GET marks the aluno's
  messages as read and shows the conversation, 404 for an unknown aluno;
  POST appends as ``autor="coach"`` and redirects (303); an empty ``texto``
  re-renders with an error and persists nothing.
- The coach's roster (``/alunos``) shows an unread badge for an aluno with
  unread messages from that aluno.

Same isolation pattern as tests/test_area_aluno.py: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on setup/teardown. Logging
in as a student for the messaging routes requires patching
``current_user`` in *three* places, since ``from ... import current_user``
binds a separate name per importing module: the gate's own reference
(``kairos.auth.middleware``), the student area's home route
(``kairos.area_aluno.routes``, used by the "Recado do coach" card tests),
and the messaging routes themselves (``kairos.mensagens.routes``).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.mensagens.service import (
    ValidationError,
    alunos_com_nao_lidas,
    contar_nao_lidas,
    enviar_mensagem,
    listar_conversa,
    marcar_lidas,
    ultima_do_coach,
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
    (``kairos.area_aluno.routes``), and the messaging routes' directly-
    imported reference (``kairos.mensagens.routes``): each ``from ...
    import current_user`` binds a separate name that a patch on the origin
    module does not reach.
    """
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)
    monkeypatch.setattr("kairos.mensagens.routes.current_user", fake_current_user)


# ---------------------------------------------------------------------------
# 1. Service: enviar_mensagem + listar_conversa + validation
# ---------------------------------------------------------------------------


def test_enviar_mensagem_persists_and_listar_conversa_returns_chronological_order(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        enviar_mensagem(aluno["id"], "aluno", "Oi, treinador!")
        enviar_mensagem(aluno["id"], "coach", "Oi, Marcos! Tudo bem?")
        enviar_mensagem(aluno["id"], "aluno", "Tudo sim.")

        conversa = listar_conversa(aluno["id"])

    assert [m["texto"] for m in conversa] == [
        "Oi, treinador!",
        "Oi, Marcos! Tudo bem?",
        "Tudo sim.",
    ]
    assert [m["autor"] for m in conversa] == ["aluno", "coach", "aluno"]
    assert all(m["lida"] is False for m in conversa)


def test_enviar_mensagem_rejects_invalid_autor_and_persists_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            enviar_mensagem(aluno["id"], "outro", "Alguma coisa")

        assert listar_conversa(aluno["id"]) == []


@pytest.mark.parametrize("texto_vazio", ["", "   ", None])
def test_enviar_mensagem_rejects_empty_texto_and_persists_nothing(
    data_dir: Path, texto_vazio
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError):
            enviar_mensagem(aluno["id"], "aluno", texto_vazio)

        assert listar_conversa(aluno["id"]) == []


# ---------------------------------------------------------------------------
# 2. Service: marcar_lidas + contar_nao_lidas (symmetric both sides)
# ---------------------------------------------------------------------------


def test_marcar_lidas_by_aluno_only_marks_coach_messages(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        enviar_mensagem(aluno["id"], "coach", "Mensagem 1 do coach")
        enviar_mensagem(aluno["id"], "coach", "Mensagem 2 do coach")
        enviar_mensagem(aluno["id"], "aluno", "Mensagem do aluno")

        assert contar_nao_lidas(aluno["id"], "aluno") == 2
        # The aluno's own message is not "unread for the coach" via this call
        # -- unrelated counter, checked separately below.

        n = marcar_lidas(aluno["id"], "aluno")

        assert n == 2
        assert contar_nao_lidas(aluno["id"], "aluno") == 0

        conversa = listar_conversa(aluno["id"])
        aluno_msg = next(m for m in conversa if m["autor"] == "aluno")
        assert aluno_msg["lida"] is False  # untouched by marcar_lidas(..., "aluno")


def test_marcar_lidas_by_coach_only_marks_aluno_messages(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        enviar_mensagem(aluno["id"], "aluno", "Mensagem 1 do aluno")
        enviar_mensagem(aluno["id"], "aluno", "Mensagem 2 do aluno")
        enviar_mensagem(aluno["id"], "coach", "Mensagem do coach")

        assert contar_nao_lidas(aluno["id"], "coach") == 2

        n = marcar_lidas(aluno["id"], "coach")

        assert n == 2
        assert contar_nao_lidas(aluno["id"], "coach") == 0

        conversa = listar_conversa(aluno["id"])
        coach_msg = next(m for m in conversa if m["autor"] == "coach")
        assert coach_msg["lida"] is False  # untouched by marcar_lidas(..., "coach")


# ---------------------------------------------------------------------------
# 3. Service: ultima_do_coach + alunos_com_nao_lidas
# ---------------------------------------------------------------------------


def test_ultima_do_coach_returns_most_recent_or_none(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        assert ultima_do_coach(aluno["id"]) is None

        enviar_mensagem(aluno["id"], "coach", "Primeira mensagem")
        enviar_mensagem(aluno["id"], "aluno", "Resposta do aluno")
        enviar_mensagem(aluno["id"], "coach", "Segunda mensagem")

        ultima = ultima_do_coach(aluno["id"])

    assert ultima is not None
    assert ultima["texto"] == "Segunda mensagem"


def test_alunos_com_nao_lidas_maps_aluno_id_to_unread_count_for_two_alunos(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")

        enviar_mensagem(aluno_a["id"], "aluno", "Mensagem 1 de A")
        enviar_mensagem(aluno_a["id"], "aluno", "Mensagem 2 de A")
        enviar_mensagem(aluno_b["id"], "aluno", "Mensagem de B")
        # A coach message must not count towards the "aluno wrote" badge.
        enviar_mensagem(aluno_b["id"], "coach", "Resposta do coach")

        mapa = alunos_com_nao_lidas()

    assert mapa == {aluno_a["id"]: 2, aluno_b["id"]: 1}


def test_alunos_com_nao_lidas_excludes_alunos_whose_messages_are_all_read(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        enviar_mensagem(aluno["id"], "aluno", "Oi")
        marcar_lidas(aluno["id"], "coach")

        mapa = alunos_com_nao_lidas()

    assert aluno["id"] not in mapa


# ---------------------------------------------------------------------------
# 4. Student side: GET /aluno/mensagens shows own conversation + marks read
# ---------------------------------------------------------------------------


def test_get_aluno_mensagens_shows_own_conversation_and_marks_coach_messages_read(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        enviar_mensagem(aluno["id"], "coach", "Bem-vindo, Marcos!")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/mensagens")

        assert response.status_code == 200
        assert "Bem-vindo, Marcos!" in response.text

        unread_after = contar_nao_lidas(aluno["id"], "aluno")

    assert unread_after == 0


# ---------------------------------------------------------------------------
# 5. Student side: POST /aluno/mensagens sends + validates
# ---------------------------------------------------------------------------


def test_post_aluno_mensagens_with_text_redirects_and_saves_as_aluno_author(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/mensagens",
            data={"texto": "Oi, treinador, tenho uma dúvida."},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/aluno/mensagens"

        conversa = listar_conversa(aluno["id"])

    assert len(conversa) == 1
    assert conversa[0]["autor"] == "aluno"
    assert conversa[0]["texto"] == "Oi, treinador, tenho uma dúvida."


def test_post_aluno_mensagens_with_empty_text_does_not_redirect_and_saves_nothing(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            "/aluno/mensagens", data={"texto": ""}, follow_redirects=False
        )

    assert response.status_code != 303
    assert "location" not in response.headers
    assert listar_conversa(aluno["id"]) == []


# ---------------------------------------------------------------------------
# 6. Student side isolation: session's aluno_id only, never another aluno
# ---------------------------------------------------------------------------


def test_aluno_mensagens_never_shows_another_alunos_conversation(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        enviar_mensagem(aluno_b["id"], "coach", "SEGREDO_DO_ALUNO_B")

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.get("/aluno/mensagens")

    assert response.status_code == 200
    assert "SEGREDO_DO_ALUNO_B" not in response.text


# ---------------------------------------------------------------------------
# 7. Home: "Recado do coach" card
# ---------------------------------------------------------------------------


def test_aluno_home_shows_recado_do_coach_card_when_unread_message_exists(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The home shows the "Recado do coach" card with the coach's latest
    message excerpt and a "novo" badge while it is unread."""
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        enviar_mensagem(aluno["id"], "coach", "Não esqueça do treino amanhã!")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Recado do coach" in response.text
    assert "novo" in response.text
    # The excerpt of the coach's message shows in the card.
    assert "Não esqueça do treino amanhã!" in response.text


def test_aluno_home_omits_recado_do_coach_card_without_coach_message(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno")

    assert response.status_code == 200
    assert "Recado do coach" not in response.text


# ---------------------------------------------------------------------------
# 8. Coach side: GET /alunos/{id}/mensagens shows conversation + marks read
# ---------------------------------------------------------------------------


def test_get_coach_mensagens_shows_conversation_and_marks_aluno_messages_read(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        enviar_mensagem(aluno["id"], "aluno", "Preciso remarcar a sessão.")

        response = client.get(f"/alunos/{aluno['id']}/mensagens")

        assert response.status_code == 200
        assert "Preciso remarcar a sessão." in response.text

        unread_after = contar_nao_lidas(aluno["id"], "coach")

    assert unread_after == 0


def test_get_coach_mensagens_returns_404_for_unknown_aluno(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999999/mensagens")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 9. Coach side: POST /alunos/{id}/mensagens sends + validates
# ---------------------------------------------------------------------------


def test_post_coach_mensagens_with_text_redirects_and_saves_as_coach_author(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")

        response = client.post(
            f"/alunos/{aluno['id']}/mensagens",
            data={"texto": "Combinado, vamos remarcar."},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/alunos/{aluno['id']}/mensagens"

        conversa = listar_conversa(aluno["id"])

    assert len(conversa) == 1
    assert conversa[0]["autor"] == "coach"
    assert conversa[0]["texto"] == "Combinado, vamos remarcar."


def test_post_coach_mensagens_with_empty_text_does_not_redirect_and_saves_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")

        response = client.post(
            f"/alunos/{aluno['id']}/mensagens",
            data={"texto": ""},
            follow_redirects=False,
        )

    assert response.status_code != 303
    assert "location" not in response.headers
    assert listar_conversa(aluno["id"]) == []


# ---------------------------------------------------------------------------
# 10. Coach roster: unread badge for alunos with unread messages
# ---------------------------------------------------------------------------


def test_alunos_roster_shows_unread_badge_for_aluno_with_unread_message(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        enviar_mensagem(aluno["id"], "aluno", "Oi, treinador!")

        response = client.get("/alunos")

    assert response.status_code == 200
    assert "badge-msgs-nao-lidas" in response.text
    assert "1 nova" in response.text


def test_alunos_roster_omits_unread_badge_for_aluno_without_unread_messages(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        create_aluno(name="Marcos Vieira")

        response = client.get("/alunos")

    assert response.status_code == 200
    assert "badge-msgs-nao-lidas" not in response.text
