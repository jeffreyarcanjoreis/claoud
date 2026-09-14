"""Tests for issue 02: the coach's planilha grouped into the 5 training phases.

- GET /alunos/{aluno_id}/treino/{treino_id} shows the planilha grouped into
  the canonical phases (each with its label and guiding question), an add
  form with a ``<select name="fase">``, and the apresentação block.
- POST .../itens accepts an optional ``fase``: a valid one makes the item
  show up under that phase; an invalid one is rejected (400, nothing saved);
  a missing one lands under "Sem fase".
- POST .../apresentacao sets/clears the workout's ``observacao`` and is
  reflected on the planilha page.
- 404 guards apply the same as the rest of the "treinos" domain (another
  student's workout, or a workout that does not exist).

Isolation pattern shared with the other suites (see test_treinos_planilha.py
and conftest.py): KAIROS_DATA_DIR points at a tmp_path, and every test is
auto-logged-in as a coach.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.treinos.service import (
    create_exercicio,
    create_treino,
    get_treino,
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
# 1. Planilha grouped by phase                                                #
# --------------------------------------------------------------------------- #

def test_planilha_shows_phase_labels_perguntas_and_select(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")

        response = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert response.status_code == 200
    assert "Skill" in response.text
    assert "Ápice" in response.text
    assert "Este corpo está pronto?" in response.text
    assert '<select id="fase" name="fase">' in response.text


# --------------------------------------------------------------------------- #
# 2. Adding an item with a valid fase                                         #
# --------------------------------------------------------------------------- #

def test_add_item_with_valid_fase_appears_under_that_phase(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Agachamento pistol")
        treino = create_treino(aluno["id"], nome="Treino A")

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens",
            data={"exercicio_id": str(ex["id"]), "fase": "skill"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        detail_page = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert "Agachamento pistol" in detail_page.text
    skill_pos = detail_page.text.find("Skill")
    exercise_pos = detail_page.text.find("Agachamento pistol")
    assert skill_pos != -1 and exercise_pos != -1 and skill_pos < exercise_pos

    detail = get_treino_detail(treino["id"])
    assert len(detail["itens"]) == 1
    assert detail["itens"][0]["fase"] == "skill"


# --------------------------------------------------------------------------- #
# 3. Adding an item with an invalid fase                                      #
# --------------------------------------------------------------------------- #

def test_add_item_with_invalid_fase_rejected_and_not_saved(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens",
            data={"exercicio_id": str(ex["id"]), "fase": "xpto"},
            follow_redirects=False,
        )

    assert response.status_code == 400
    detail = get_treino_detail(treino["id"])
    assert detail["itens"] == []


# --------------------------------------------------------------------------- #
# 4. Adding an item without a fase                                            #
# --------------------------------------------------------------------------- #

def test_add_item_without_fase_lands_under_sem_fase(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Prancha")
        treino = create_treino(aluno["id"], nome="Treino A")

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens",
            data={"exercicio_id": str(ex["id"])},
            follow_redirects=False,
        )
        assert response.status_code == 303

        detail_page = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert "Sem fase" in detail_page.text
    assert "Prancha" in detail_page.text

    detail = get_treino_detail(treino["id"])
    assert len(detail["itens"]) == 1
    assert detail["itens"][0]["fase"] is None


# --------------------------------------------------------------------------- #
# 5. Apresentação                                                             #
# --------------------------------------------------------------------------- #

def test_set_apresentacao_persists_and_shows_on_planilha(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/apresentacao",
            data={"apresentacao": "Hoje foco em técnica e respiração."},
            follow_redirects=False,
        )
        assert response.status_code == 303

        detail_page = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert get_treino(treino["id"])["observacao"] == "Hoje foco em técnica e respiração."
    assert "Hoje foco em técnica e respiração." in detail_page.text


def test_set_apresentacao_with_blank_text_clears_it(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A", observacao="Texto antigo")

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/apresentacao",
            data={"apresentacao": "   "},
            follow_redirects=False,
        )
        assert response.status_code == 303

    assert get_treino(treino["id"])["observacao"] is None


# --------------------------------------------------------------------------- #
# 6. 404 guards                                                               #
# --------------------------------------------------------------------------- #

def test_get_planilha_404_for_another_alunos_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        dono = create_aluno(name="Dono")
        outro = create_aluno(name="Outro")
        treino = create_treino(dono["id"], nome="Treino do Dono")

        response = client.get(f"/alunos/{outro['id']}/treino/{treino['id']}")
    assert response.status_code == 404


def test_get_planilha_404_for_missing_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        response = client.get(f"/alunos/{aluno['id']}/treino/9999")
    assert response.status_code == 404


def test_set_apresentacao_404_for_another_alunos_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        dono = create_aluno(name="Dono")
        outro = create_aluno(name="Outro")
        treino = create_treino(dono["id"], nome="Treino do Dono")

        response = client.post(
            f"/alunos/{outro['id']}/treino/{treino['id']}/apresentacao",
            data={"apresentacao": "texto"},
            follow_redirects=False,
        )
    assert response.status_code == 404
    assert get_treino(treino["id"])["observacao"] is None


def test_set_apresentacao_404_for_missing_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        response = client.post(
            f"/alunos/{aluno['id']}/treino/9999/apresentacao",
            data={"apresentacao": "texto"},
            follow_redirects=False,
        )
    assert response.status_code == 404
