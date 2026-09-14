"""Tests for issue 07: the coach describing base/regressão/progressão
variations per workout item.

Covers the functional specification:

- ``update_item(..., variacao_base=..., variacao_regressao=...,
  variacao_progressao=...)`` persists the three variations (raw string ->
  ``_normalize`` -> ``None`` when blank/whitespace-only), reflected by
  ``get_treino_detail``; updating again with different values overwrites
  them; sending blank strings clears them back to ``None``;
- ``get_treino_detail``: an item with no variations exposes all three keys
  as ``None`` (no fabricated defaults, rule 6);
- ``GET .../itens/{item_id}/editar`` pre-fills the three textareas with the
  item's current variation text;
- ``POST .../itens/{item_id}`` (edit form) persists the three variation
  fields, and sending them blank clears them;
- the coach's planilha (``aluno_detalhe.html``) and the student's read-only
  planilha (``area_aluno/treino_detalhe.html``) show a "Variações" block
  only when at least one variation is filled in, and only the filled-in
  ones are printed -- no placeholder text when none exist (edge case in
  the issue's spec).

Isolation pattern shared with the other treino suites: KAIROS_DATA_DIR
points at a temp dir and the cached engine is disposed on setup/teardown
(see tests/test_treino_editar_item.py and tests/test_treino_fase.py). The
aluno-side login override follows tests/test_treino_aluno_fases.py.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.treinos.service import (
    add_item_to_treino,
    create_exercicio,
    create_treino,
    get_treino_detail,
    update_item,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def _login_as_aluno(monkeypatch: pytest.MonkeyPatch, aluno_id) -> None:
    """Same pattern as tests/test_treino_aluno_fases.py: override the
    suite-wide auto-login-as-coach patch with a student session, patching
    both the gate's reference and the route module's directly-imported one.
    """
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)


# --------------------------------------------------------------------------- #
# 1. Service: update_item persists/clears the three variations             #
# --------------------------------------------------------------------------- #


def test_update_item_persists_all_three_variations(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        result = update_item(
            item["id"],
            variacao_base="Supino reto com barra",
            variacao_regressao="Supino com halteres, amplitude reduzida",
            variacao_progressao="Supino com pausa no peito",
        )

        assert result["variacao_base"] == "Supino reto com barra"
        assert result["variacao_regressao"] == "Supino com halteres, amplitude reduzida"
        assert result["variacao_progressao"] == "Supino com pausa no peito"

        detail = get_treino_detail(treino["id"])

    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_base"] == "Supino reto com barra"
    assert updated["variacao_regressao"] == "Supino com halteres, amplitude reduzida"
    assert updated["variacao_progressao"] == "Supino com pausa no peito"


@pytest.mark.parametrize(
    "field", ["variacao_base", "variacao_regressao", "variacao_progressao"]
)
@pytest.mark.parametrize("blank_value", ["", "   "])
def test_update_item_with_blank_or_whitespace_variation_normalizes_to_none(
    data_dir: Path, field: str, blank_value: str
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        kwargs = {
            "variacao_base": "Base",
            "variacao_regressao": "Regressão",
            "variacao_progressao": "Progressão",
        }
        kwargs[field] = blank_value

        result = update_item(item["id"], **kwargs)

    assert result[field] is None
    for other in ["variacao_base", "variacao_regressao", "variacao_progressao"]:
        if other != field:
            assert result[other] is not None


def test_update_item_overwrites_variations_on_second_call(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        update_item(
            item["id"],
            variacao_base="Base 1",
            variacao_regressao="Regressão 1",
            variacao_progressao="Progressão 1",
        )
        result = update_item(
            item["id"],
            variacao_base="Base 2",
            variacao_regressao="Regressão 2",
            variacao_progressao="Progressão 2",
        )

        detail = get_treino_detail(treino["id"])

    assert result["variacao_base"] == "Base 2"
    assert result["variacao_regressao"] == "Regressão 2"
    assert result["variacao_progressao"] == "Progressão 2"
    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_base"] == "Base 2"
    assert updated["variacao_regressao"] == "Regressão 2"
    assert updated["variacao_progressao"] == "Progressão 2"


def test_update_item_clears_variations_when_sent_blank(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        update_item(
            item["id"],
            variacao_base="Base",
            variacao_regressao="Regressão",
            variacao_progressao="Progressão",
        )
        result = update_item(
            item["id"],
            variacao_base="",
            variacao_regressao="",
            variacao_progressao="",
        )

        detail = get_treino_detail(treino["id"])

    assert result["variacao_base"] is None
    assert result["variacao_regressao"] is None
    assert result["variacao_progressao"] is None
    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_base"] is None
    assert updated["variacao_regressao"] is None
    assert updated["variacao_progressao"] is None


# --------------------------------------------------------------------------- #
# 2. get_treino_detail: item without variations exposes all three as None  #
# --------------------------------------------------------------------------- #


def test_get_treino_detail_item_without_variations_exposes_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        detail = get_treino_detail(treino["id"])

    item = detail["itens"][0]
    assert item["variacao_base"] is None
    assert item["variacao_regressao"] is None
    assert item["variacao_progressao"] is None


# --------------------------------------------------------------------------- #
# 3. GET edit form pre-fills the three textareas                           #
# --------------------------------------------------------------------------- #


def test_edit_form_prefills_current_variations(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(
            item["id"],
            variacao_base="Supino reto com barra",
            variacao_regressao="Supino com halteres",
            variacao_progressao="Supino com pausa",
        )

        response = client.get(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{item['id']}/editar"
        )

    assert response.status_code == 200
    assert "Supino reto com barra" in response.text
    assert "Supino com halteres" in response.text
    assert "Supino com pausa" in response.text


def test_edit_form_with_no_variations_leaves_textareas_empty(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        response = client.get(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{item['id']}/editar"
        )

    assert response.status_code == 200
    assert '<textarea id="variacao_base" name="variacao_base" rows="2"></textarea>' in response.text
    assert '<textarea id="variacao_regressao" name="variacao_regressao" rows="2"></textarea>' in response.text
    assert '<textarea id="variacao_progressao" name="variacao_progressao" rows="2"></textarea>' in response.text


# --------------------------------------------------------------------------- #
# 4. POST edit form: persists the three variation fields, blanks clear      #
# --------------------------------------------------------------------------- #


def test_update_item_route_persists_variations(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{item['id']}",
            data={
                "series": "3",
                "fase": "skill",
                "variacao_base": "Supino reto com barra",
                "variacao_regressao": "Supino com halteres",
                "variacao_progressao": "Supino com pausa",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    detail = get_treino_detail(treino["id"])
    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_base"] == "Supino reto com barra"
    assert updated["variacao_regressao"] == "Supino com halteres"
    assert updated["variacao_progressao"] == "Supino com pausa"


def test_update_item_route_with_blank_variations_clears_them(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(
            item["id"],
            variacao_base="Base",
            variacao_regressao="Regressão",
            variacao_progressao="Progressão",
        )

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{item['id']}",
            data={
                "series": "3",
                "fase": "skill",
                "variacao_base": "",
                "variacao_regressao": "",
                "variacao_progressao": "",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    detail = get_treino_detail(treino["id"])
    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["variacao_base"] is None
    assert updated["variacao_regressao"] is None
    assert updated["variacao_progressao"] is None


# --------------------------------------------------------------------------- #
# 5. Coach's planilha (aluno_detalhe.html): "Variações" block                #
# --------------------------------------------------------------------------- #


def test_coach_planilha_shows_variacoes_block_when_filled(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(item["id"], variacao_base="Supino reto com barra")

        response = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert response.status_code == 200
    assert "Variações" in response.text
    assert "Supino reto com barra" in response.text


def test_coach_planilha_omits_variacoes_block_when_none_filled(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        response = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert response.status_code == 200
    assert "Variações" not in response.text


def test_coach_planilha_shows_only_the_filled_variation(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(item["id"], variacao_regressao="Supino com halteres")

        response = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert response.status_code == 200
    assert "Variações" in response.text
    assert "Supino com halteres" in response.text
    assert ">Base<" not in response.text
    assert ">Progressão<" not in response.text


# --------------------------------------------------------------------------- #
# 6. Student's read-only planilha (area_aluno/treino_detalhe.html)          #
# --------------------------------------------------------------------------- #


def test_aluno_planilha_shows_variacoes_block_when_filled(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        update_item(
            item["id"],
            variacao_base="Supino reto com barra",
            variacao_progressao="Supino com pausa",
        )

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 200
    assert "Variações" in response.text
    assert "Supino reto com barra" in response.text
    assert "Supino com pausa" in response.text


def test_aluno_planilha_omits_variacoes_block_when_none_filled(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 200
    assert "Variações" not in response.text
