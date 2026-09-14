"""Tests for issue 05: the coach reordering exercises within a phase.

- Service ``mover_item(item_id, direcao)``: swaps ``ordem`` with the
  immediate neighbour in the *same* treino and *same* phase (``fase`` may be
  ``None``, meaning "Sem fase" -- its own group). No-op (returns False) at
  either end of the phase's group, or when the item does not exist. An
  invalid ``direcao`` raises :class:`ValidationError` before touching the
  session.
- Route ``POST /alunos/{aluno_id}/treino/{treino_id}/itens/{item_id}/mover``
  (form ``direcao``): get-or-404 in the domain's usual pattern (aluno,
  treino belongs to aluno, item belongs to treino), then delegates to
  ``mover_item``; always redirects (303) back to the planilha, including at
  the edges and for a tampered ``direcao`` (no-op, no error).

Isolation pattern shared with the other suites (see test_treino_editar_item.py
and test_treino_coach_fases.py): KAIROS_DATA_DIR points at a tmp_path, and
every test is auto-logged-in as a coach (see conftest.py).
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
    get_treino_detail,
    mover_item,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def _ordem_by_id(treino_id: int) -> dict:
    detalhe = get_treino_detail(treino_id)
    return {item["id"]: item["ordem"] for item in detalhe["itens"]}


# --------------------------------------------------------------------------- #
# 1. mover_item: basic swap within the same phase                            #
# --------------------------------------------------------------------------- #


def test_mover_item_up_swaps_order_with_previous_in_same_phase(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        top = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="skill")
        bottom = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="skill"
        )

        before = _ordem_by_id(treino["id"])
        assert before[top["id"]] < before[bottom["id"]]

        result = mover_item(bottom["id"], "cima")

        after = _ordem_by_id(treino["id"])

    assert result is True
    assert after[bottom["id"]] == before[top["id"]]
    assert after[top["id"]] == before[bottom["id"]]


def test_mover_item_down_swaps_order_with_next_in_same_phase(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        top = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="skill")
        bottom = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="skill"
        )

        before = _ordem_by_id(treino["id"])

        result = mover_item(top["id"], "baixo")

        after = _ordem_by_id(treino["id"])

    assert result is True
    assert after[top["id"]] == before[bottom["id"]]
    assert after[bottom["id"]] == before[top["id"]]


# --------------------------------------------------------------------------- #
# 2. mover_item: edges are a no-op                                           #
# --------------------------------------------------------------------------- #


def test_mover_item_first_up_is_noop(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        top = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="skill")
        bottom = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="skill"
        )

        before = _ordem_by_id(treino["id"])

        result = mover_item(top["id"], "cima")

        after = _ordem_by_id(treino["id"])

    assert result is False
    assert after == before


def test_mover_item_last_down_is_noop(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        top = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="skill")
        bottom = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="skill"
        )

        before = _ordem_by_id(treino["id"])

        result = mover_item(bottom["id"], "baixo")

        after = _ordem_by_id(treino["id"])

    assert result is False
    assert after == before


# --------------------------------------------------------------------------- #
# 3. mover_item: a neighbour in a DIFFERENT phase is never touched            #
# --------------------------------------------------------------------------- #


def test_mover_item_does_not_cross_into_another_phase(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        # Fase A has a single item; fase B's items surround it in "ordem"
        # (lower and higher), but must not be treated as neighbours.
        antes = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="aquecimento"
        )
        sozinho = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="skill"
        )
        depois = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="aquecimento"
        )

        before = _ordem_by_id(treino["id"])

        result_up = mover_item(sozinho["id"], "cima")
        result_down = mover_item(sozinho["id"], "baixo")

        after = _ordem_by_id(treino["id"])

    assert result_up is False
    assert result_down is False
    assert after == before
    # sanity: the "aquecimento" items really do straddle the "skill" one
    assert before[antes["id"]] < before[sozinho["id"]] < before[depois["id"]]


# --------------------------------------------------------------------------- #
# 4. mover_item: items without a phase form their own "Sem fase" group       #
# --------------------------------------------------------------------------- #


def test_mover_item_within_sem_fase_group_works(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        top = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        bottom = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        before = _ordem_by_id(treino["id"])

        result = mover_item(bottom["id"], "cima")

        after = _ordem_by_id(treino["id"])

    assert result is True
    assert after[bottom["id"]] == before[top["id"]]
    assert after[top["id"]] == before[bottom["id"]]


def test_mover_item_without_phase_does_not_cross_into_a_phased_item(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        # Added first, so its "ordem" is lower than the "Sem fase" item's.
        com_fase = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="skill"
        )
        sem_fase = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        before = _ordem_by_id(treino["id"])

        result = mover_item(sem_fase["id"], "cima")

        after = _ordem_by_id(treino["id"])

    assert result is False
    assert after == before


# --------------------------------------------------------------------------- #
# 5. mover_item: invalid direction / missing item                            #
# --------------------------------------------------------------------------- #


def test_mover_item_with_invalid_direction_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        with pytest.raises(ValidationError, match="Direção inválida"):
            mover_item(item["id"], "esquerda")


def test_mover_item_for_missing_item_returns_false(data_dir: Path) -> None:
    with TestClient(app):
        result = mover_item(999999, "cima")

    assert result is False


# --------------------------------------------------------------------------- #
# 6. Route: form redirects and actually moves the item                       #
# --------------------------------------------------------------------------- #


def test_move_route_up_redirects_and_swaps_order(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        top = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="skill")
        bottom = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="skill"
        )
        before = _ordem_by_id(treino["id"])

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{bottom['id']}/mover",
            data={"direcao": "cima"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == f"/alunos/{aluno['id']}/treino/{treino['id']}"
    after = _ordem_by_id(treino["id"])
    assert after[bottom["id"]] == before[top["id"]]
    assert after[top["id"]] == before[bottom["id"]]


def test_move_route_down_redirects_and_swaps_order(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        top = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="skill")
        bottom = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="skill"
        )
        before = _ordem_by_id(treino["id"])

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{top['id']}/mover",
            data={"direcao": "baixo"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == f"/alunos/{aluno['id']}/treino/{treino['id']}"
    after = _ordem_by_id(treino["id"])
    assert after[top["id"]] == before[bottom["id"]]
    assert after[bottom["id"]] == before[top["id"]]


# --------------------------------------------------------------------------- #
# 7. Route: edges redirect without error and change nothing                  #
# --------------------------------------------------------------------------- #


def test_move_route_first_up_redirects_and_is_noop(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        top = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        before = _ordem_by_id(treino["id"])

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{top['id']}/mover",
            data={"direcao": "cima"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert _ordem_by_id(treino["id"]) == before


def test_move_route_last_down_redirects_and_is_noop(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        bottom = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        before = _ordem_by_id(treino["id"])

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{bottom['id']}/mover",
            data={"direcao": "baixo"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert _ordem_by_id(treino["id"]) == before


# --------------------------------------------------------------------------- #
# 8. Route: ownership guard (item of another student's workout) -> 404       #
# --------------------------------------------------------------------------- #


def test_move_route_404_for_item_of_another_alunos_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        dono = create_aluno(name="Dono")
        outro = create_aluno(name="Outro")
        ex = create_exercicio(nome="Supino")
        treino_dono = create_treino(dono["id"], nome="Treino do Dono")
        top = add_item_to_treino(treino_dono["id"], exercicio_id=str(ex["id"]))
        bottom = add_item_to_treino(treino_dono["id"], exercicio_id=str(ex["id"]))
        before = _ordem_by_id(treino_dono["id"])

        response = client.post(
            f"/alunos/{outro['id']}/treino/{treino_dono['id']}/itens/{bottom['id']}/mover",
            data={"direcao": "cima"},
            follow_redirects=False,
        )

    assert response.status_code == 404
    assert _ordem_by_id(treino_dono["id"]) == before


def test_move_route_404_for_missing_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        response = client.post(
            f"/alunos/{aluno['id']}/treino/9999/itens/1/mover",
            data={"direcao": "cima"},
            follow_redirects=False,
        )
    assert response.status_code == 404


def test_move_route_404_for_missing_item(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/9999/mover",
            data={"direcao": "cima"},
            follow_redirects=False,
        )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# 9. Route: tampered direction is a no-op (redirects, changes nothing)       #
# --------------------------------------------------------------------------- #


def test_move_route_with_invalid_direction_is_noop_and_redirects(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        top = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        before = _ordem_by_id(treino["id"])

        response = client.post(
            f"/alunos/{aluno['id']}/treino/{treino['id']}/itens/{top['id']}/mover",
            data={"direcao": "xyz"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == f"/alunos/{aluno['id']}/treino/{treino['id']}"
    assert _ordem_by_id(treino["id"]) == before
