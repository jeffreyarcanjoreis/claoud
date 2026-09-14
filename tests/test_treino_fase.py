"""Tests for the "fase" (workout phase) domain -- issue 01.

Covers the functional specification for the service layer
(``kairos.treinos.service``); this issue is data + service only (no
routes/UI):

- ``add_item_to_treino(..., fase=...)`` accepts any of ``FASE_OPCOES``,
  returning ``fase``/``fase_label`` in the dict, reflected by
  ``get_treino_detail``;
- an empty string or omitted ``fase`` normalizes to ``None``
  ("Sem fase" -- no label);
- an unknown ``fase`` raises :class:`ValidationError` and nothing is
  persisted (the item never shows up in the workout's detail);
- ``agrupar_itens_por_fase`` groups items into the five canonical phases,
  in :data:`FASE_OPCOES` order (even when a phase's group is empty), with
  a trailing "Sem fase" group appended only when at least one item has no
  phase, preserving each group's internal (insertion) order;
- ``set_apresentacao`` writes/clears ``Treino.observacao``, normalizing
  blank text to ``None``, and returns ``None`` for a workout that does not
  exist.

Isolation: KAIROS_DATA_DIR points at a temp dir and the cached engine is
disposed on setup/teardown (same pattern as tests/test_treinos_planilha.py
and tests/test_nivel.py).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.treinos.service import (
    FASE_LABELS,
    FASE_OPCOES,
    FASE_PERGUNTAS,
    ValidationError,
    add_item_to_treino,
    agrupar_itens_por_fase,
    create_exercicio,
    create_treino,
    get_treino,
    get_treino_detail,
    set_apresentacao,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


# --------------------------------------------------------------------------- #
# constants                                                                    #
# --------------------------------------------------------------------------- #


def test_fase_opcoes_are_the_five_documented_phases_in_order() -> None:
    assert FASE_OPCOES == (
        "preparacao",
        "aquecimento",
        "skill",
        "apice",
        "volta_a_calma",
    )


def test_fase_labels_cover_every_option() -> None:
    assert set(FASE_LABELS) == set(FASE_OPCOES)
    assert FASE_LABELS["skill"] == "Skill"
    assert FASE_LABELS["volta_a_calma"] == "Volta à calma"


def test_fase_perguntas_cover_every_option() -> None:
    assert set(FASE_PERGUNTAS) == set(FASE_OPCOES)


# --------------------------------------------------------------------------- #
# 1. add_item_to_treino: valid fase                                            #
# --------------------------------------------------------------------------- #


def test_add_item_with_valid_fase_returns_fase_and_label(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")

        item = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="skill"
        )

        assert item["fase"] == "skill"
        assert item["fase_label"] == "Skill"

        detail = get_treino_detail(treino["id"])

    assert detail["itens"][0]["fase"] == "skill"
    assert detail["itens"][0]["fase_label"] == "Skill"


@pytest.mark.parametrize("fase_valida", FASE_OPCOES)
def test_add_item_accepts_every_documented_fase_option(
    data_dir: Path, fase_valida: str
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")

        item = add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase=fase_valida
        )

    assert item["fase"] == fase_valida
    assert item["fase_label"] == FASE_LABELS[fase_valida]


# --------------------------------------------------------------------------- #
# 2. add_item_to_treino: blank/omitted fase normalizes to None                 #
# --------------------------------------------------------------------------- #


def test_add_item_with_blank_fase_is_none(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")

        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="")

        assert item["fase"] is None
        assert item["fase_label"] is None

        detail = get_treino_detail(treino["id"])

    assert detail["itens"][0]["fase"] is None
    assert detail["itens"][0]["fase_label"] is None


def test_add_item_without_fase_argument_is_none(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")

        item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

    assert item["fase"] is None
    assert item["fase_label"] is None


# --------------------------------------------------------------------------- #
# 3. add_item_to_treino: invalid fase rejected, nothing persisted             #
# --------------------------------------------------------------------------- #


def test_add_item_with_invalid_fase_raises_and_persists_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")

        with pytest.raises(ValidationError, match="Fase inválida"):
            add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="xpto")

        detail = get_treino_detail(treino["id"])

    assert detail["itens"] == []


# --------------------------------------------------------------------------- #
# 4. agrupar_itens_por_fase                                                    #
# --------------------------------------------------------------------------- #


def test_agrupar_itens_por_fase_returns_five_groups_in_canonical_order_even_when_empty() -> (
    None
):
    grupos = agrupar_itens_por_fase([])

    assert len(grupos) == 5
    assert [g["fase"] for g in grupos] == list(FASE_OPCOES)
    for grupo, fase in zip(grupos, FASE_OPCOES):
        assert grupo["fase_label"] == FASE_LABELS[fase]
        assert grupo["fase_pergunta"] == FASE_PERGUNTAS[fase]
        assert grupo["itens"] == []


def test_agrupar_itens_por_fase_places_items_in_matching_groups_and_preserves_order() -> (
    None
):
    itens = [
        {"id": 1, "fase": "skill"},
        {"id": 2, "fase": "aquecimento"},
        {"id": 3, "fase": "skill"},
    ]

    grupos = agrupar_itens_por_fase(itens)

    by_fase = {g["fase"]: g for g in grupos}
    assert [i["id"] for i in by_fase["skill"]["itens"]] == [1, 3]
    assert [i["id"] for i in by_fase["aquecimento"]["itens"]] == [2]
    assert by_fase["preparacao"]["itens"] == []
    assert by_fase["apice"]["itens"] == []
    assert by_fase["volta_a_calma"]["itens"] == []
    # no "Sem fase" group appended: every item has a phase
    assert all(g["fase"] is not None for g in grupos)
    assert len(grupos) == 5


def test_agrupar_itens_por_fase_appends_sem_fase_group_only_when_needed() -> None:
    itens = [
        {"id": 1, "fase": "skill"},
        {"id": 2, "fase": None},
    ]

    grupos = agrupar_itens_por_fase(itens)

    assert len(grupos) == 6
    sem_fase = grupos[-1]
    assert sem_fase["fase"] is None
    assert sem_fase["fase_label"] == "Sem fase"
    assert [i["id"] for i in sem_fase["itens"]] == [2]
    # still in canonical order before the trailing group
    assert [g["fase"] for g in grupos[:5]] == list(FASE_OPCOES)


def test_agrupar_itens_por_fase_treats_empty_string_fase_as_sem_fase() -> None:
    itens = [{"id": 1, "fase": ""}]

    grupos = agrupar_itens_por_fase(itens)

    assert len(grupos) == 6
    assert grupos[-1]["fase"] is None
    assert grupos[-1]["fase_label"] == "Sem fase"
    assert [i["id"] for i in grupos[-1]["itens"]] == [1]


def test_agrupar_itens_por_fase_preserves_insertion_order_within_a_group() -> None:
    itens = [
        {"id": 10, "fase": "aquecimento"},
        {"id": 11, "fase": "aquecimento"},
        {"id": 12, "fase": "aquecimento"},
    ]

    grupos = agrupar_itens_por_fase(itens)

    aquecimento = next(g for g in grupos if g["fase"] == "aquecimento")
    assert [i["id"] for i in aquecimento["itens"]] == [10, 11, 12]


def test_agrupar_itens_por_fase_end_to_end_with_get_treino_detail(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")

        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]), fase="skill")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        add_item_to_treino(
            treino["id"], exercicio_id=str(ex["id"]), fase="aquecimento"
        )

        detail = get_treino_detail(treino["id"])
        grupos = agrupar_itens_por_fase(detail["itens"])

    assert len(grupos) == 6
    assert [g["fase"] for g in grupos[:5]] == list(FASE_OPCOES)
    assert grupos[-1]["fase"] is None
    assert grupos[-1]["fase_label"] == "Sem fase"
    by_fase = {g["fase"]: g for g in grupos}
    assert len(by_fase["skill"]["itens"]) == 1
    assert len(by_fase["aquecimento"]["itens"]) == 1
    assert len(by_fase[None]["itens"]) == 1


# --------------------------------------------------------------------------- #
# 5. set_apresentacao                                                          #
# --------------------------------------------------------------------------- #


def test_set_apresentacao_persists_text(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")

        set_apresentacao(treino["id"], "Foco em base")

        atualizado = get_treino(treino["id"])

    assert atualizado["observacao"] == "Foco em base"


def test_set_apresentacao_with_blank_text_clears_to_none(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")

        set_apresentacao(treino["id"], "Foco em base")
        set_apresentacao(treino["id"], "  ")

        atualizado = get_treino(treino["id"])

    assert atualizado["observacao"] is None


def test_set_apresentacao_for_missing_treino_returns_none(data_dir: Path) -> None:
    with TestClient(app):
        resultado = set_apresentacao(999999, "x")

    assert resultado is None
