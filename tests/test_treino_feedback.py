"""Tests for issue 12: the coach's feedback on a student's execution attachment.

Covers set_feedback_anexo (service), feedback_coach exposure in the anexo dicts,
the coach POST route (gate, 404s, 303) and the student's read-only view.
Every test points KAIROS_DATA_DIR at a temp dir.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.execucao.service import (
    adicionar_anexo,
    anexos_do_treino,
    get_anexo,
    list_anexos,
    set_feedback_anexo,
)
from kairos.main import app
from kairos.treinos.service import add_item_to_treino, create_exercicio, create_treino

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def _login_as_aluno(monkeypatch: pytest.MonkeyPatch, aluno_id) -> None:
    fake = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake)


def _setup(nome: str = "Ana"):
    aluno = create_aluno(name=nome)
    ex = create_exercicio(nome=f"Supino {nome}")
    treino = create_treino(aluno["id"], nome="Treino A")
    item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
    anexo = adicionar_anexo(item["id"], PNG_BYTES, "image/png", "x.png")
    return aluno, treino, item, anexo


def _url(aluno, anexo) -> str:
    return f"/alunos/{aluno['id']}/anexos/{anexo['id']}/feedback"


def _planilha(client, aluno, treino):
    return client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")


# --------------------------------------------------------------------------- #
# 1. Service                                                                  #
# --------------------------------------------------------------------------- #


def test_new_anexo_has_no_feedback(data_dir: Path) -> None:
    with TestClient(app):
        _, _, _, anexo = _setup()
        assert get_anexo(anexo["id"])["feedback_coach"] is None


def test_set_feedback_anexo_persists_and_returns_dict(data_dir: Path) -> None:
    with TestClient(app):
        _, _, _, anexo = _setup()
        result = set_feedback_anexo(anexo["id"], "Boa execução, cuide do joelho.")
        loaded = get_anexo(anexo["id"])

    assert result["id"] == anexo["id"]
    assert result["feedback_coach"] == "Boa execução, cuide do joelho."
    assert loaded["feedback_coach"] == "Boa execução, cuide do joelho."


def test_set_feedback_anexo_overwrites_previous_feedback(data_dir: Path) -> None:
    with TestClient(app):
        _, _, _, anexo = _setup()
        set_feedback_anexo(anexo["id"], "Primeiro")
        set_feedback_anexo(anexo["id"], "Segundo")
        loaded = get_anexo(anexo["id"])

    assert loaded["feedback_coach"] == "Segundo"


@pytest.mark.parametrize("empty", [None, "", "   ", "\n\t "])
def test_set_feedback_anexo_empty_clears_to_none(data_dir: Path, empty) -> None:
    with TestClient(app):
        _, _, _, anexo = _setup()
        set_feedback_anexo(anexo["id"], "Algo")
        result = set_feedback_anexo(anexo["id"], empty)
        loaded = get_anexo(anexo["id"])

    assert result["feedback_coach"] is None
    assert loaded["feedback_coach"] is None


def test_set_feedback_anexo_default_argument_clears(data_dir: Path) -> None:
    with TestClient(app):
        _, _, _, anexo = _setup()
        set_feedback_anexo(anexo["id"], "Algo")
        set_feedback_anexo(anexo["id"])
        assert get_anexo(anexo["id"])["feedback_coach"] is None


def test_set_feedback_anexo_unknown_id_returns_none(data_dir: Path) -> None:
    with TestClient(app):
        assert set_feedback_anexo(999999, "x") is None


def test_set_feedback_anexo_does_not_touch_other_anexos(data_dir: Path) -> None:
    with TestClient(app):
        _, _, item, anexo = _setup()
        other = adicionar_anexo(item["id"], PNG_BYTES, "image/png", "y.png")
        set_feedback_anexo(anexo["id"], "Só neste")
        assert get_anexo(other["id"])["feedback_coach"] is None


def test_list_anexos_exposes_feedback_coach(data_dir: Path) -> None:
    with TestClient(app):
        _, _, item, anexo = _setup()
        set_feedback_anexo(anexo["id"], "Feedback lista")
        rows = list_anexos(item["id"])

    assert rows[0]["feedback_coach"] == "Feedback lista"


def test_anexos_do_treino_exposes_feedback_coach(data_dir: Path) -> None:
    with TestClient(app):
        _, treino, item, anexo = _setup()
        set_feedback_anexo(anexo["id"], "Feedback treino")
        mapa = anexos_do_treino(treino["id"])

    assert mapa[item["id"]][0]["feedback_coach"] == "Feedback treino"


# --------------------------------------------------------------------------- #
# 2. Coach route                                                              #
# --------------------------------------------------------------------------- #


def test_coach_post_feedback_redirects_and_planilha_shows_text(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno, treino, _, anexo = _setup()
        response = client.post(
            _url(aluno, anexo),
            data={"feedback": "Mantenha a coluna neutra"},
            follow_redirects=False,
        )
        stored = get_anexo(anexo["id"])
        page = _planilha(client, aluno, treino)

    assert response.status_code == 303
    assert response.headers["location"] == f"/alunos/{aluno['id']}/treino/{treino['id']}"
    assert stored["feedback_coach"] == "Mantenha a coluna neutra"
    assert page.status_code == 200
    assert f"/alunos/{aluno['id']}/anexos/{anexo['id']}/feedback" in page.text
    assert 'name="feedback"' in page.text
    assert "Mantenha a coluna neutra" in page.text
    assert "Salvar feedback" in page.text


def test_coach_post_feedback_overwrites_existing(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno, _, _, anexo = _setup()
        client.post(_url(aluno, anexo), data={"feedback": "Antigo"}, follow_redirects=False)
        client.post(_url(aluno, anexo), data={"feedback": "Novo"}, follow_redirects=False)
        stored = get_anexo(anexo["id"])

    assert stored["feedback_coach"] == "Novo"


@pytest.mark.parametrize("empty", ["", "   "])
def test_coach_post_empty_feedback_clears(data_dir: Path, empty) -> None:
    with TestClient(app) as client:
        aluno, treino, _, anexo = _setup()
        set_feedback_anexo(anexo["id"], "Texto antigo único")
        response = client.post(
            _url(aluno, anexo), data={"feedback": empty}, follow_redirects=False
        )
        stored = get_anexo(anexo["id"])
        page = _planilha(client, aluno, treino)

    assert response.status_code == 303
    assert stored["feedback_coach"] is None
    assert "Texto antigo único" not in page.text


def test_coach_planilha_prefills_existing_feedback_in_textarea(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno, treino, _, anexo = _setup()
        set_feedback_anexo(anexo["id"], "Pré-preenchido")
        page = _planilha(client, aluno, treino)

    assert f'name="feedback" rows="3" placeholder' in page.text or 'name="feedback"' in page.text
    assert "Pré-preenchido</textarea>" in page.text


def test_coach_post_feedback_for_anexo_of_other_aluno_returns_404(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno_a, _, _, _ = _setup("Aluno A")
        _, _, _, anexo_b = _setup("Aluno B")
        response = client.post(
            _url(aluno_a, anexo_b), data={"feedback": "Invasão"}, follow_redirects=False
        )
        stored = get_anexo(anexo_b["id"])

    assert response.status_code == 404
    assert stored["feedback_coach"] is None


def test_coach_post_feedback_unknown_anexo_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno, _, _, _ = _setup()
        response = client.post(
            f"/alunos/{aluno['id']}/anexos/999999/feedback",
            data={"feedback": "x"},
            follow_redirects=False,
        )

    assert response.status_code == 404


def test_coach_post_feedback_unknown_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        _, _, _, anexo = _setup()
        response = client.post(
            f"/alunos/999999/anexos/{anexo['id']}/feedback",
            data={"feedback": "x"},
            follow_redirects=False,
        )
        stored = get_anexo(anexo["id"])

    assert response.status_code == 404
    assert stored["feedback_coach"] is None


# --------------------------------------------------------------------------- #
# 3. Student reads                                                            #
# --------------------------------------------------------------------------- #


def test_aluno_sees_feedback_after_coach_posts(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, _, anexo = _setup()
        client.post(
            _url(aluno, anexo),
            data={"feedback": "Ótimo registro, siga assim"},
            follow_redirects=False,
        )
        _login_as_aluno(monkeypatch, aluno["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.status_code == 200
    assert "Feedback do coach" in page.text
    assert "Ótimo registro, siga assim" in page.text
    assert 'name="feedback"' not in page.text


def test_aluno_without_feedback_does_not_see_box(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, _, _ = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.status_code == 200
    assert "Feedback do coach" not in page.text


def test_aluno_does_not_see_box_after_feedback_cleared(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, _, anexo = _setup()
        set_feedback_anexo(anexo["id"], "Temporário")
        set_feedback_anexo(anexo["id"], "")
        _login_as_aluno(monkeypatch, aluno["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert "Feedback do coach" not in page.text
    assert "Temporário" not in page.text


def test_aluno_sees_feedback_only_on_the_anexo_that_has_it(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, item, anexo = _setup()
        adicionar_anexo(item["id"], PNG_BYTES, "image/png", "y.png")
        set_feedback_anexo(anexo["id"], "Só no primeiro")
        _login_as_aluno(monkeypatch, aluno["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.text.count("Feedback do coach") == 1
