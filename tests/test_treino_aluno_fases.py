"""Tests for issue 03: the student's own workout planilha shown in phases.

Covers the functional specification:

- ``GET /aluno/treinos/{treino_id}`` (read-only, aluno of the session): shows
  the planilha grouped into the 5 phases (labels + guiding question), the
  workout's apresentação at the top (when present), and the coach's
  observação on each exercise;
- an item without a phase falls into a "Sem fase" group;
- a workout without an apresentação simply omits that block, still 200;
- isolation: another aluno's workout (or a nonexistent one) -> 404, via the
  generic "not found" page (``_nao_encontrado``).

Isolation pattern shared with the other suites: KAIROS_DATA_DIR points at a
temp dir and the cached engine is disposed on setup/teardown.
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
    set_apresentacao,
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

    Patches the gate's own reference (``kairos.auth.middleware``) and the
    student area route's directly-imported reference
    (``kairos.area_aluno.routes``): each ``from ... import current_user``
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
# 1. Full scenario: phase label + guiding question + exercise + observação +
#    apresentação
# ---------------------------------------------------------------------------


def test_treino_detalhe_shows_fase_label_pergunta_observacao_and_apresentacao(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Souza")
        ex = create_exercicio(nome="Prancha")
        treino = create_treino(aluno["id"], nome="Treino A")
        set_apresentacao(treino["id"], "Estabilidade antes de carga")
        add_item_to_treino(
            treino["id"],
            exercicio_id=str(ex["id"]),
            fase="skill",
            observacao="foco na postura",
        )

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 200
    assert "Skill" in response.text
    assert "Este corpo está pronto?" in response.text
    assert "Prancha" in response.text
    assert "foco na postura" in response.text
    assert "Estabilidade antes de carga" in response.text


# ---------------------------------------------------------------------------
# 2. Item without a phase falls into "Sem fase"
# ---------------------------------------------------------------------------


def test_treino_detalhe_item_without_fase_falls_into_sem_fase_group(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Souza")
        ex = create_exercicio(nome="Corrida leve")
        treino = create_treino(aluno["id"], nome="Treino B")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 200
    assert "Sem fase" in response.text
    assert "Corrida leve" in response.text


# ---------------------------------------------------------------------------
# 3. Workout without apresentação omits that block, still 200
# ---------------------------------------------------------------------------


def test_treino_detalhe_without_apresentacao_omits_that_block(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Souza")
        ex = create_exercicio(nome="Agachamento")
        treino = create_treino(aluno["id"], nome="Treino C")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="apice")

        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 200
    assert "Estabilidade antes de carga" not in response.text
    assert "Ápice" in response.text


# ---------------------------------------------------------------------------
# 4. Isolation: another aluno's workout / a nonexistent workout -> 404
# ---------------------------------------------------------------------------


def test_treino_detalhe_of_another_aluno_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")
        treino_b = create_treino(aluno_b["id"], nome="Treino de B")

        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.get(f"/aluno/treinos/{treino_b['id']}")

    assert response.status_code == 404


def test_treino_detalhe_of_nonexistent_treino_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Souza")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.get("/aluno/treinos/9999")

    assert response.status_code == 404
