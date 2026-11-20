"""Tests for the session arc (duracao + minutes per phase) -- issue 13.

Data + service only: ``set_duracao``, ``arco_da_sessao``, ``PROPORCOES_FASE``
and the ``duracao_min`` field exposed by ``get_treino``/``get_treino_detail``.

Isolation: KAIROS_DATA_DIR points at a temp dir and the cached engine is
disposed on setup/teardown.
"""

from pathlib import Path

import pytest

import kairos.db
from kairos.migrations_runner import run_migrations
from kairos.alunos.service import create_aluno
from kairos.treinos.service import (
    DURACAO_OPCOES,
    FASE_LABELS,
    FASE_OPCOES,
    FASE_PERGUNTAS,
    PROPORCOES_FASE,
    ValidationError,
    arco_da_sessao,
    create_treino,
    get_treino,
    get_treino_detail,
    set_duracao,
)

EXPECTED_MINUTOS = {
    30: [3, 5, 7, 10, 5],
    45: [4, 7, 11, 16, 7],
    60: [5, 9, 15, 22, 9],
}


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    run_migrations()
    yield target
    kairos.db.dispose_engine()


@pytest.fixture
def treino(data_dir: Path) -> dict:
    aluno = create_aluno(name="Ana")
    return create_treino(aluno["id"], nome="Treino A")


# --------------------------------------------------------------------------- #
# constants                                                                    #
# --------------------------------------------------------------------------- #


def test_duracao_opcoes_are_30_45_60() -> None:
    assert DURACAO_OPCOES == (30, 45, 60)


def test_proporcoes_fase_matches_canonical_table() -> None:
    assert set(PROPORCOES_FASE) == {30, 45, 60}
    for duracao, minutos in EXPECTED_MINUTOS.items():
        assert [PROPORCOES_FASE[duracao][f] for f in FASE_OPCOES] == minutos


@pytest.mark.parametrize("duracao", [30, 45, 60])
def test_proporcoes_fase_sum_equals_duration(duracao: int) -> None:
    assert sum(PROPORCOES_FASE[duracao].values()) == duracao


# --------------------------------------------------------------------------- #
# set_duracao                                                                  #
# --------------------------------------------------------------------------- #


def test_new_treino_has_no_duracao(treino: dict) -> None:
    assert get_treino(treino["id"])["duracao_min"] is None


@pytest.mark.parametrize("duracao", [30, 45, 60])
def test_set_duracao_persists_valid_option(treino: dict, duracao: int) -> None:
    result = set_duracao(treino["id"], duracao)

    assert result is not None
    assert result["duracao_min"] == duracao
    assert get_treino(treino["id"])["duracao_min"] == duracao


def test_set_duracao_accepts_numeric_string(treino: dict) -> None:
    result = set_duracao(treino["id"], "45")

    assert result["duracao_min"] == 45
    assert get_treino(treino["id"])["duracao_min"] == 45


def test_set_duracao_accepts_int(treino: dict) -> None:
    set_duracao(treino["id"], 60)

    assert get_treino(treino["id"])["duracao_min"] == 60


def test_set_duracao_can_change_value(treino: dict) -> None:
    set_duracao(treino["id"], 30)
    set_duracao(treino["id"], 60)

    assert get_treino(treino["id"])["duracao_min"] == 60


@pytest.mark.parametrize("empty", ["", None, "   "])
def test_set_duracao_empty_clears_to_none(treino: dict, empty) -> None:
    set_duracao(treino["id"], 45)

    result = set_duracao(treino["id"], empty)

    assert result is not None
    assert result["duracao_min"] is None
    assert get_treino(treino["id"])["duracao_min"] is None


def test_set_duracao_default_argument_clears(treino: dict) -> None:
    set_duracao(treino["id"], 45)

    set_duracao(treino["id"])

    assert get_treino(treino["id"])["duracao_min"] is None


@pytest.mark.parametrize("invalid", [50, "abc", 0, -30, 31, "45.5", 90])
def test_set_duracao_invalid_raises_and_persists_nothing(
    treino: dict, invalid
) -> None:
    with pytest.raises(ValidationError):
        set_duracao(treino["id"], invalid)

    assert get_treino(treino["id"])["duracao_min"] is None


def test_set_duracao_invalid_keeps_previous_value(treino: dict) -> None:
    set_duracao(treino["id"], 45)

    with pytest.raises(ValidationError):
        set_duracao(treino["id"], 50)

    assert get_treino(treino["id"])["duracao_min"] == 45


def test_set_duracao_invalid_message(treino: dict) -> None:
    with pytest.raises(ValidationError, match="Duração inválida"):
        set_duracao(treino["id"], "abc")


def test_set_duracao_unknown_treino_returns_none(data_dir: Path) -> None:
    assert set_duracao(9999, 45) is None


# --------------------------------------------------------------------------- #
# arco_da_sessao                                                               #
# --------------------------------------------------------------------------- #


def test_arco_without_duracao_is_none(treino: dict) -> None:
    assert arco_da_sessao(treino["id"]) is None


def test_arco_after_clearing_duracao_is_none(treino: dict) -> None:
    set_duracao(treino["id"], 45)
    set_duracao(treino["id"], "")

    assert arco_da_sessao(treino["id"]) is None


def test_arco_unknown_treino_is_none(data_dir: Path) -> None:
    assert arco_da_sessao(9999) is None


@pytest.mark.parametrize("duracao", [30, 45, 60])
def test_arco_has_five_phases_in_canonical_order(
    treino: dict, duracao: int
) -> None:
    set_duracao(treino["id"], duracao)

    arco = arco_da_sessao(treino["id"])

    assert arco is not None
    assert len(arco) == 5
    assert [p["fase"] for p in arco] == [
        "preparacao",
        "aquecimento",
        "skill",
        "apice",
        "volta_a_calma",
    ]


@pytest.mark.parametrize("duracao", [30, 45, 60])
def test_arco_minutes_match_canonical_table(treino: dict, duracao: int) -> None:
    set_duracao(treino["id"], duracao)

    arco = arco_da_sessao(treino["id"])

    assert [p["minutos"] for p in arco] == EXPECTED_MINUTOS[duracao]


@pytest.mark.parametrize("duracao", [30, 45, 60])
def test_arco_minutes_sum_equals_duration(treino: dict, duracao: int) -> None:
    set_duracao(treino["id"], duracao)

    arco = arco_da_sessao(treino["id"])

    assert sum(p["minutos"] for p in arco) == duracao


def test_arco_phases_carry_label_and_question(treino: dict) -> None:
    set_duracao(treino["id"], 45)

    arco = arco_da_sessao(treino["id"])

    for entry in arco:
        assert set(entry) == {
            "fase",
            "fase_label",
            "fase_pergunta",
            "minutos",
            "ajustado",
        }
        assert entry["fase_label"] == FASE_LABELS[entry["fase"]]
        assert entry["fase_pergunta"] == FASE_PERGUNTAS[entry["fase"]]
    assert arco[2]["fase_label"] == "Skill"
    assert arco[4]["fase_label"] == "Volta à calma"


def test_arco_follows_duration_changes(treino: dict) -> None:
    set_duracao(treino["id"], 30)
    assert arco_da_sessao(treino["id"])[3]["minutos"] == 10

    set_duracao(treino["id"], 60)
    assert arco_da_sessao(treino["id"])[3]["minutos"] == 22


# --------------------------------------------------------------------------- #
# get_treino / get_treino_detail                                               #
# --------------------------------------------------------------------------- #


def test_get_treino_exposes_duracao_min(treino: dict) -> None:
    assert "duracao_min" in get_treino(treino["id"])
    set_duracao(treino["id"], 60)

    assert get_treino(treino["id"])["duracao_min"] == 60


def test_get_treino_detail_exposes_duracao_min(treino: dict) -> None:
    assert get_treino_detail(treino["id"])["duracao_min"] is None
    set_duracao(treino["id"], 30)

    assert get_treino_detail(treino["id"])["duracao_min"] == 30


def test_create_treino_dict_exposes_duracao_min_none(treino: dict) -> None:
    assert treino["duracao_min"] is None
