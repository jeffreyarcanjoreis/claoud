"""Tests for issue 04: the coach editing a single workout item in-place.

- GET /alunos/{aluno_id}/treino/{treino_id}/itens/{item_id}/editar returns a
  form pre-filled with the item's current values and a ``<select
  name="fase">``.
- POST .../itens/{item_id} (form: series, reps, carga, observacao, fase)
  edits the item in-place: success redirects (303) to the workout detail;
  an invalid fase or a non-positive series count is rejected (400) and
  nothing is persisted.
- Ownership guards apply: reaching an item that belongs to another student's
  workout (via GET or POST) is a 404.

Isolation pattern shared with the other suites (see test_treino_coach_fases.py
and test_treinos_planilha.py): KAIROS_DATA_DIR points at a tmp_path, and
every test is auto-logged-in as a coach.
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
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


# --------------------------------------------------------------------------- #
# 1. GET edit form pre-filled                                                 #
# --------------------------------------------------------------------------- #

def test_edit_form_shows_current_values_and_fase_select(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="preparacao", series="2"
        )

        response = client.get(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{item['id']}/editar"
        )

    assert response.status_code == 200
    assert 'value="2"' in response.text
    assert '<select id="fase" name="fase">' in response.text
    assert "Supino" in response.text


def test_edit_form_404_for_missing_item(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")

        response = client.get(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/9999/editar"
        )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# 2. POST edits in-place on success                                          #
# --------------------------------------------------------------------------- #

def test_update_item_success_redirects_and_persists(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="preparacao", series="2"
        )

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{item['id']}",
            data={
                "series": "4",
                "reps": "8-10",
                "carga": "20 kg",
                "observacao": "cadência",
                "fase": "skill",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == f"/alunos/{aluno['id']}/treino/{treino['id']}"

    detail = get_treino_detail(treino["id"])
    updated = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert updated["series"] == 4
    assert updated["reps"] == "8-10"
    assert updated["carga"] == "20 kg"
    assert updated["observacao"] == "cadência"
    assert updated["fase"] == "skill"


# --------------------------------------------------------------------------- #
# 3. POST with invalid fase                                                  #
# --------------------------------------------------------------------------- #

def test_update_item_with_invalid_fase_rejected_and_unchanged(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="preparacao", series="2"
        )

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{item['id']}",
            data={
                "series": "4",
                "reps": "8-10",
                "carga": "20 kg",
                "observacao": "cadência",
                "fase": "xpto",
            },
            follow_redirects=False,
        )

    assert response.status_code == 400

    detail = get_treino_detail(treino["id"])
    unchanged = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert unchanged["series"] == 2
    assert unchanged["fase"] == "preparacao"
    assert unchanged["reps"] is None
    assert unchanged["carga"] is None
    assert unchanged["observacao"] is None


# --------------------------------------------------------------------------- #
# 4. POST with non-positive series                                          #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("bad_series", ["0", "-1"])
def test_update_item_with_non_positive_series_rejected_and_unchanged(
    data_dir: Path, bad_series: str
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="preparacao", series="2"
        )

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{item['id']}",
            data={"series": bad_series, "fase": "skill"},
            follow_redirects=False,
        )

    assert response.status_code == 400

    detail = get_treino_detail(treino["id"])
    unchanged = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert unchanged["series"] == 2
    assert unchanged["fase"] == "preparacao"


# --------------------------------------------------------------------------- #
# 5. Isolation: another student's workout item                               #
# --------------------------------------------------------------------------- #

def test_get_edit_form_404_for_item_of_another_alunos_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        dono = create_aluno(name="Dono")
        outro = create_aluno(name="Outro")
        ex = create_exercicio(nome="Supino")
        treino_dono = create_treino(dono["id"], nome="Treino do Dono")
        item = add_item_to_treino(treino_dono["id"], exercicio_id=str(ex["id"]))

        response = client.get(
            f"/alunos/{outro['id']}/treino/{treino_dono['id']}/itens/{item['id']}/editar"
        )
    assert response.status_code == 404


def test_post_edit_404_for_item_of_another_alunos_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        dono = create_aluno(name="Dono")
        outro = create_aluno(name="Outro")
        ex = create_exercicio(nome="Supino")
        treino_dono = create_treino(dono["id"], nome="Treino do Dono")
        item = add_item_to_treino(
            treino_dono["id"], exercicio_id=str(ex["id"]), series="2"
        )

        response = client.post(
            f"/alunos/{outro['id']}/treino/{treino_dono['id']}/itens/{item['id']}",
            data={"series": "5", "fase": "skill"},
            follow_redirects=False,
        )
    assert response.status_code == 404

    detail = get_treino_detail(treino_dono["id"])
    unchanged = next(i for i in detail["itens"] if i["id"] == item["id"])
    assert unchanged["series"] == 2
    assert unchanged["fase"] is None
