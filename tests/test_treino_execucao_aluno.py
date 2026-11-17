"""Tests for issue 10: the student's execution UI on the workout page.

Covers: POST .../itens/{item_id}/execucao (feito checkbox present/absent,
carga/reps/observacao, upsert, 303 redirect, 404 for another aluno's treino or
an item outside the treino) and the GET page reflecting it (checked checkbox,
prefill, "registrado hoje" badge, "Feitos: X de Y" progress with bar only when
total > 0, empty fields without fake placeholders).
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.execucao.service import get_execucao, list_execucoes
from kairos.main import app
from kairos.treinos.service import add_item_to_treino, create_exercicio, create_treino


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def _login_as_aluno(monkeypatch: pytest.MonkeyPatch, aluno_id) -> None:
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)


def _setup(n_items: int = 1):
    aluno = create_aluno(name="Ana")
    ex = create_exercicio(nome="Supino")
    treino = create_treino(aluno["id"], nome="Treino A")
    itens = [
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        for _ in range(n_items)
    ]
    return aluno, treino, itens


def _url(treino, item) -> str:
    return f"/aluno/treinos/{treino['id']}/itens/{item['id']}/execucao"


def _form_html(html: str, treino, item) -> str:
    """Return the execution <form> markup for one item."""
    action = f'action="/aluno/treinos/{treino["id"]}/itens/{item["id"]}/execucao"'
    start = html.index(action)
    end = html.index("</form>", start)
    return html[start:end]


def _checkbox_checked(form: str) -> bool:
    tag = re.search(r'<input[^>]*name="feito"[^>]*>', form).group(0)
    return re.search(r"\bchecked\b", tag) is not None


def _input_value(form: str, name: str) -> str:
    tag = re.search(rf'<input[^>]*name="{name}"[^>]*>', form).group(0)
    return re.search(r'value="([^"]*)"', tag).group(1)


def _textarea(form: str) -> str:
    return re.search(r"<textarea[^>]*>(.*?)</textarea>", form, re.S).group(1)


# --------------------------------------------------------------------------- #
# 1. POST persists and GET reflects                                         #
# --------------------------------------------------------------------------- #


def test_post_execucao_redirects_and_get_reflects_values(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, (item,) = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            _url(treino, item),
            data={
                "feito": "on",
                "carga_real": "20kg",
                "reps_real": "3x10",
                "observacao": "Foi tranquilo",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == f"/aluno/treinos/{treino['id']}"

        page = client.get(f"/aluno/treinos/{treino['id']}")
        saved = get_execucao(item["id"])

    assert page.status_code == 200
    form = _form_html(page.text, treino, item)
    assert _checkbox_checked(form)
    assert _input_value(form, "carga_real") == "20kg"
    assert _input_value(form, "reps_real") == "3x10"
    assert _textarea(form) == "Foi tranquilo"
    assert "registrado hoje" in form
    assert saved["feito"] is True
    assert saved["carga_real"] == "20kg"
    assert saved["reps_real"] == "3x10"
    assert saved["observacao"] == "Foi tranquilo"


def test_post_execucao_feito_without_carga_reps_stores_null(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, (item,) = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        client.post(
            _url(treino, item),
            data={"feito": "on", "carga_real": "", "reps_real": "", "observacao": "  "},
            follow_redirects=False,
        )
        saved = get_execucao(item["id"])

    assert saved["feito"] is True
    assert saved["carga_real"] is None
    assert saved["reps_real"] is None
    assert saved["observacao"] is None


# --------------------------------------------------------------------------- #
# 2. Progress                                                               #
# --------------------------------------------------------------------------- #


def test_progress_shows_feitos_k_of_n_with_bar(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, itens = _setup(3)
        _login_as_aluno(monkeypatch, aluno["id"])

        before = client.get(f"/aluno/treinos/{treino['id']}").text
        for item in itens[:2]:
            client.post(_url(treino, item), data={"feito": "on"}, follow_redirects=False)
        # Third item registered but NOT done: must not count.
        client.post(_url(treino, itens[2]), data={"carga_real": "10"}, follow_redirects=False)
        after = client.get(f"/aluno/treinos/{treino['id']}").text

    assert "Feitos: 0 de 3" in before
    assert "Feitos: 2 de 3" in after
    assert "progresso-barra" in after
    assert "width: 67%" in after


# --------------------------------------------------------------------------- #
# 3. Absent checkbox                                                        #
# --------------------------------------------------------------------------- #


def test_post_without_feito_field_stores_feito_false_with_carga_and_reps(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, (item,) = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            _url(treino, item),
            data={"carga_real": "15kg", "reps_real": "8"},
            follow_redirects=False,
        )
        saved = get_execucao(item["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 303
    assert saved["feito"] is False
    assert saved["carga_real"] == "15kg"
    assert saved["reps_real"] == "8"
    form = _form_html(page.text, treino, item)
    assert not _checkbox_checked(form)
    assert _input_value(form, "carga_real") == "15kg"
    assert "registrado hoje" in form
    assert "Feitos: 0 de 1" in page.text


def test_unchecking_feito_on_resubmit_sets_feito_false(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, (item,) = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        client.post(_url(treino, item), data={"feito": "on"}, follow_redirects=False)
        client.post(_url(treino, item), data={}, follow_redirects=False)
        saved = get_execucao(item["id"])

    assert saved["feito"] is False


# --------------------------------------------------------------------------- #
# 4. Upsert                                                                 #
# --------------------------------------------------------------------------- #


def test_second_post_same_day_updates_instead_of_duplicating(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, (item,) = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        client.post(
            _url(treino, item),
            data={"feito": "on", "carga_real": "10kg", "observacao": "primeira"},
            follow_redirects=False,
        )
        client.post(
            _url(treino, item),
            data={"feito": "on", "carga_real": "12kg", "observacao": "segunda"},
            follow_redirects=False,
        )
        rows = list_execucoes(item["id"])

    assert len(rows) == 1
    assert rows[0]["carga_real"] == "12kg"
    assert rows[0]["observacao"] == "segunda"


# --------------------------------------------------------------------------- #
# 5. 404s                                                                   #
# --------------------------------------------------------------------------- #


def test_post_execucao_on_another_alunos_treino_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        ex = create_exercicio(nome="Supino")
        treino_b = create_treino(aluno_b["id"], nome="Treino de B")
        item_b = add_item_to_treino(treino_b["id"], exercicio_id=str(ex["id"]))

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.post(
            _url(treino_b, item_b), data={"feito": "on"}, follow_redirects=False
        )
        rows = list_execucoes(item_b["id"])

    assert response.status_code == 404
    assert rows == []


def test_post_execucao_for_item_outside_treino_in_url_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino_a = create_treino(aluno["id"], nome="Treino A")
        treino_b = create_treino(aluno["id"], nome="Treino B")
        item_b = add_item_to_treino(treino_b["id"], exercicio_id=str(ex["id"]))

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            _url(treino_a, item_b), data={"feito": "on"}, follow_redirects=False
        )
        rows = list_execucoes(item_b["id"])

    assert response.status_code == 404
    assert rows == []


def test_post_execucao_for_nonexistent_item_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, _ = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            f"/aluno/treinos/{treino['id']}/itens/99999/execucao",
            data={"feito": "on"},
            follow_redirects=False,
        )

    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# 6. Empty states                                                           #
# --------------------------------------------------------------------------- #


def test_treino_without_items_shows_zero_of_zero_and_no_bar(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Vazio")
        _login_as_aluno(monkeypatch, aluno["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.status_code == 200
    assert "Feitos: 0 de 0" in page.text
    assert "progresso-barra" not in page.text


def test_item_without_execution_has_empty_fields_and_no_badge(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, (item,) = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.status_code == 200
    form = _form_html(page.text, treino, item)
    assert not _checkbox_checked(form)
    assert _input_value(form, "carga_real") == ""
    assert _input_value(form, "reps_real") == ""
    assert _textarea(form) == ""
    assert "placeholder" not in form
    assert "registrado hoje" not in page.text
    assert "progresso-barra" in page.text
    assert "Feitos: 0 de 1" in page.text
