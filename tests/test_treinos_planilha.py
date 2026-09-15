"""Tests for montar treinos (slice 9.2): service + routes.

- service: create requires a name; listing carries the item count; the detail
  joins items to exercise names in order; adding an item requires a valid
  library exercise and increments the order; sets must be positive; removing an
  item and deleting a whole workout.
- routes: the "Treino" sub-tab (empty state and 404), creating a workout
  (redirect to its detail), rejecting a blank name, adding an exercise (visible
  in the planilha), rejecting an add with no exercise chosen, removing an item,
  ownership guards (another student's workout / another workout's item -> 404),
  and the sub-nav tab.

Isolation pattern shared with the other suites.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.treinos.service import (
    ValidationError,
    add_item_to_treino,
    create_exercicio,
    create_treino,
    delete_treino,
    get_treino_detail,
    list_treinos,
    remove_item,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


# --------------------------------------------------------------------------- #
# service                                                                      #
# --------------------------------------------------------------------------- #

def test_create_treino_requires_nome(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        with pytest.raises(ValidationError):
            create_treino(aluno["id"], nome="   ")


def test_list_treinos_carries_item_count(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        treinos = list_treinos(aluno["id"])
        assert len(treinos) == 1
        assert treinos[0]["item_count"] == 1


def test_add_item_increments_order_and_joins_exercise(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        e1 = create_exercicio(nome="Supino", grupo_muscular="Peito")
        e2 = create_exercicio(nome="Agachamento")
        treino = create_treino(aluno["id"], nome="Treino A")

        add_item_to_treino(treino["id"], exercicio_id=str(e1["id"]), series="4", reps="8-10")
        add_item_to_treino(treino["id"], exercicio_id=str(e2["id"]))

        detail = get_treino_detail(treino["id"])
        assert [i["exercicio_nome"] for i in detail["itens"]] == ["Supino", "Agachamento"]
        assert [i["ordem"] for i in detail["itens"]] == [1, 2]
        assert detail["itens"][0]["grupo_muscular"] == "Peito"
        assert detail["itens"][0]["series"] == 4
        assert detail["itens"][0]["reps"] == "8-10"


def test_add_item_rejects_missing_and_unknown_exercise(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")

        with pytest.raises(ValidationError):
            add_item_to_treino(treino["id"], exercicio_id="")
        with pytest.raises(ValidationError):
            add_item_to_treino(treino["id"], exercicio_id="9999")


def test_add_item_rejects_non_positive_series(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        with pytest.raises(ValidationError):
            add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), series="0")


def test_remove_item_and_delete_treino(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        assert remove_item(item["id"]) is True
        assert get_treino_detail(treino["id"])["itens"] == []

        assert delete_treino(treino["id"]) is True
        assert get_treino_detail(treino["id"]) is None


# --------------------------------------------------------------------------- #
# routes                                                                       #
# --------------------------------------------------------------------------- #

def test_treino_subtab_empty_state_and_nav(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        response = client.get(f"/alunos/{aluno['id']}/treino")

    assert response.status_code == 200
    assert "ainda não tem treinos" in response.text
    assert f'href="/alunos/{aluno["id"]}/treino">Treino</a>' in response.text


def test_treino_subtab_404_for_missing_aluno(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/9999/treino")
    assert response.status_code == 404


def test_create_treino_redirects_to_detail(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        response = client.post(
            f"/alunos/{aluno['id']}/treino",
            data={"nome": "Treino A"},
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/alunos/{aluno['id']}/treino/")


def test_create_treino_without_nome_rejected(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        response = client.post(
            f"/alunos/{aluno['id']}/treino",
            data={"nome": ""},
            follow_redirects=False,
        )
    assert response.status_code == 400
    assert "Nome é obrigatório." in response.text


def test_add_exercise_shows_in_planilha(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Levantamento terra", grupo_muscular="Posterior")
        treino = create_treino(aluno["id"], nome="Treino B")

        added = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens",
            data={"exercicio_id": str(ex["id"]), "series": "3", "reps": "10", "carga": "60 kg"},
            follow_redirects=False,
        )
        assert added.status_code == 303

        detail = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert "Levantamento terra" in detail.text
    assert "60 kg" in detail.text


def test_add_exercise_without_choice_rejected(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino B")

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens",
            data={"exercicio_id": ""},
            follow_redirects=False,
        )
    assert response.status_code == 400
    assert "Selecione um exercício." in response.text


def test_remove_item_via_route(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino B")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{item['id']}/remover",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert get_treino_detail(treino["id"])["itens"] == []


def test_cannot_reach_another_alunos_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        dono = create_aluno(name="Dono")
        outro = create_aluno(name="Outro")
        treino = create_treino(dono["id"], nome="Treino do Dono")

        response = client.get(f"/alunos/{outro['id']}/treino/{treino['id']}")
    assert response.status_code == 404


def test_cannot_remove_item_via_wrong_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino_a = create_treino(aluno["id"], nome="A")
        treino_b = create_treino(aluno["id"], nome="B")
        item = add_item_to_treino(treino_a["id"], exercicio_id=str(ex["id"]))

        # item belongs to treino_a, but we address it under treino_b
        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino_b['id']}/itens/{item['id']}/remover",
            follow_redirects=False,
        )
    assert response.status_code == 404
