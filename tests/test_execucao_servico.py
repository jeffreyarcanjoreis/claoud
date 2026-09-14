"""Tests for the "execucao" (per-exercise student execution log) domain --
issue 09.

Covers the functional specification:

- ``registrar_execucao`` creates a row, readable back via ``get_execucao``;
  empty strings for ``carga_real``/``reps_real``/``observacao`` normalize to
  None (rule 6), and ``feito`` is coerced to a plain bool;
- registering again on the SAME (treino_item_id, data) updates the existing
  row instead of creating a new one (upsert) -- confirmed via
  ``list_execucoes`` staying at length 1 with the updated values;
- registering on different dates produces separate rows (history), returned
  by ``list_execucoes`` ordered by date descending;
- ``get_execucao`` returns None when there is no row for the requested day;
- an inexistent ``treino_item_id`` raises ``ValidationError`` and persists
  nothing;
- ``execucoes_do_treino`` maps treino_item_id -> execution for a single
  date, covering only items with a row on that day;
- ``progresso_sessao`` returns ``{"total", "feitos"}`` for a treino on a
  given date, treating a treino with no items as ``{"total": 0, "feitos":
  0}``, and never counting an execution recorded on a different date.

Isolation: KAIROS_DATA_DIR points at a temp dir and the cached engine is
disposed on setup/teardown (same pattern as tests/test_registro_treino.py).
Every test body runs inside ``with TestClient(app):`` so the app's lifespan
creates the database file and stamps it at head, the same way
tests/test_nivel.py and tests/test_registro_treino.py do for
data+service-only slices with no dedicated routes.
"""

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.execucao.service import (
    execucoes_do_treino,
    get_execucao,
    list_execucoes,
    progresso_sessao,
    registrar_execucao,
)
from kairos.main import app
from kairos.treinos.service import (
    ValidationError,
    add_item_to_treino,
    create_exercicio,
    create_treino,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def _create_treino_item(treino_id: int, nome: str = "Agachamento") -> int:
    """Create an Exercicio and add it as an item of the given treino;
    return the treino_item's id."""
    exercicio = create_exercicio(nome=nome)
    item = add_item_to_treino(treino_id, exercicio_id=str(exercicio["id"]))
    return item["id"]


def _setup_aluno_treino_item() -> tuple[int, int]:
    """Build the minimal chain: aluno -> treino -> treino_item.

    Returns (treino_id, treino_item_id).
    """
    aluno = create_aluno(name="Marcos Vieira")
    treino = create_treino(aluno["id"], nome="Treino A")
    item_id = _create_treino_item(treino["id"])
    return treino["id"], item_id


# ---------------------------------------------------------------------------
# 1. registrar_execucao creates a row; normalization; feito coerced to bool
# ---------------------------------------------------------------------------


def test_registrar_execucao_creates_row_readable_via_get_execucao(
    data_dir: Path,
) -> None:
    with TestClient(app):
        _, item_id = _setup_aluno_treino_item()
        hoje = datetime.date.today()

        criado = registrar_execucao(
            item_id,
            feito=True,
            carga_real="20kg",
            reps_real="10",
            observacao="Foi bem hoje.",
        )

        execucao = get_execucao(item_id)

    assert criado["treino_item_id"] == item_id
    assert criado["data"] == hoje
    assert execucao is not None
    assert execucao["id"] == criado["id"]
    assert execucao["feito"] is True
    assert execucao["carga_real"] == "20kg"
    assert execucao["reps_real"] == "10"
    assert execucao["observacao"] == "Foi bem hoje."


def test_registrar_execucao_normalizes_empty_strings_to_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        _, item_id = _setup_aluno_treino_item()

        registrar_execucao(
            item_id,
            feito=True,
            carga_real="",
            reps_real="   ",
            observacao="",
        )

        execucao = get_execucao(item_id)

    assert execucao is not None
    assert execucao["carga_real"] is None
    assert execucao["reps_real"] is None
    assert execucao["observacao"] is None


@pytest.mark.parametrize(
    "raw_feito, expected", [(1, True), (0, False), (None, False)]
)
def test_registrar_execucao_coerces_feito_to_bool(
    data_dir: Path, raw_feito, expected
) -> None:
    with TestClient(app):
        _, item_id = _setup_aluno_treino_item()

        registrar_execucao(item_id, feito=raw_feito)

        execucao = get_execucao(item_id)

    assert execucao is not None
    assert execucao["feito"] is expected


# ---------------------------------------------------------------------------
# 2. Upsert: second registration on the same day updates, not duplicates
# ---------------------------------------------------------------------------


def test_registrar_execucao_twice_same_day_updates_instead_of_duplicating(
    data_dir: Path,
) -> None:
    with TestClient(app):
        _, item_id = _setup_aluno_treino_item()
        hoje = datetime.date.today()

        primeiro = registrar_execucao(
            item_id, feito=False, carga_real="10kg", data=hoje
        )
        segundo = registrar_execucao(
            item_id,
            feito=True,
            carga_real="15kg",
            observacao="Melhorou.",
            data=hoje,
        )

        historico = list_execucoes(item_id)

    assert len(historico) == 1
    assert segundo["id"] == primeiro["id"]
    assert historico[0]["feito"] is True
    assert historico[0]["carga_real"] == "15kg"
    assert historico[0]["observacao"] == "Melhorou."


# ---------------------------------------------------------------------------
# 3. Different dates -> separate rows (history), ordered date desc
# ---------------------------------------------------------------------------


def test_registrar_execucao_on_different_dates_creates_separate_history_rows(
    data_dir: Path,
) -> None:
    with TestClient(app):
        _, item_id = _setup_aluno_treino_item()
        d1 = datetime.date(2026, 9, 1)
        d2 = datetime.date(2026, 9, 5)
        d3 = datetime.date(2026, 9, 3)

        registrar_execucao(item_id, feito=True, data=d1)
        registrar_execucao(item_id, feito=True, data=d2)
        registrar_execucao(item_id, feito=True, data=d3)

        historico = list_execucoes(item_id)

    assert [e["data"] for e in historico] == [d2, d3, d1]


# ---------------------------------------------------------------------------
# 4. get_execucao returns None when there is no row for the day
# ---------------------------------------------------------------------------


def test_get_execucao_returns_none_when_no_row_for_the_day(data_dir: Path) -> None:
    with TestClient(app):
        _, item_id = _setup_aluno_treino_item()

        sem_registro_hoje = get_execucao(item_id)

        outro_dia = datetime.date(2026, 1, 1)
        registrar_execucao(item_id, feito=True, data=outro_dia)

        ainda_none_hoje = get_execucao(item_id, data=datetime.date.today())
        com_registro_outro_dia = get_execucao(item_id, data=outro_dia)

    assert sem_registro_hoje is None
    assert ainda_none_hoje is None
    assert com_registro_outro_dia is not None


# ---------------------------------------------------------------------------
# 5. Nonexistent treino_item_id -> ValidationError, nothing persisted
# ---------------------------------------------------------------------------


def test_registrar_execucao_with_nonexistent_treino_item_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError, match="Exercício não encontrado"):
            registrar_execucao(999999, feito=True)

        historico = list_execucoes(999999)

    assert historico == []


# ---------------------------------------------------------------------------
# 6. execucoes_do_treino maps treino_item_id -> execution for a given date
# ---------------------------------------------------------------------------


def test_execucoes_do_treino_maps_items_to_their_execution_on_the_given_date(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        treino = create_treino(aluno["id"], nome="Treino A")
        item1 = _create_treino_item(treino["id"], nome="Agachamento")
        item2 = _create_treino_item(treino["id"], nome="Supino")

        hoje = datetime.date.today()
        ontem = hoje - datetime.timedelta(days=1)

        registrar_execucao(item1, feito=True, data=hoje)
        registrar_execucao(item2, feito=False, data=ontem)  # different day: excluded

        mapa = execucoes_do_treino(treino["id"], data=hoje)

    assert set(mapa.keys()) == {item1}
    assert mapa[item1]["feito"] is True


def test_execucoes_do_treino_defaults_to_today(data_dir: Path) -> None:
    with TestClient(app):
        treino_id, item_id = _setup_aluno_treino_item()

        registrar_execucao(item_id, feito=True)

        mapa = execucoes_do_treino(treino_id)

    assert set(mapa.keys()) == {item_id}


# ---------------------------------------------------------------------------
# 7. progresso_sessao: total/feitos accounting
# ---------------------------------------------------------------------------


def test_progresso_sessao_counts_total_items_and_feitos_on_the_day(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        treino = create_treino(aluno["id"], nome="Treino A")
        item1 = _create_treino_item(treino["id"], nome="Agachamento")
        item2 = _create_treino_item(treino["id"], nome="Supino")
        _create_treino_item(treino["id"], nome="Remada")  # no execution today

        hoje = datetime.date.today()
        registrar_execucao(item1, feito=True, data=hoje)
        registrar_execucao(item2, feito=False, data=hoje)

        progresso = progresso_sessao(treino["id"], data=hoje)

    assert progresso == {"total": 3, "feitos": 1}


def test_progresso_sessao_for_treino_without_items_returns_zeroed_dict(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")
        treino = create_treino(aluno["id"], nome="Treino Vazio")

        progresso = progresso_sessao(treino["id"])

    assert progresso == {"total": 0, "feitos": 0}


def test_progresso_sessao_does_not_count_execution_from_another_day(
    data_dir: Path,
) -> None:
    with TestClient(app):
        treino_id, item_id = _setup_aluno_treino_item()
        ontem = datetime.date.today() - datetime.timedelta(days=1)

        registrar_execucao(item_id, feito=True, data=ontem)

        progresso_hoje = progresso_sessao(treino_id)
        progresso_ontem = progresso_sessao(treino_id, data=ontem)

    assert progresso_hoje == {"total": 1, "feitos": 0}
    assert progresso_ontem == {"total": 1, "feitos": 1}
