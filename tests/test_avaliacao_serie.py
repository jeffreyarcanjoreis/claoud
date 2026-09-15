"""Tests for issue 01: chronological series of an Aluno's Avaliacoes.

Covers the functional specification of ``avaliacao_series(aluno_id)``:
- returns the Aluno's assessments in ascending chronological order (data
  asc, tie-broken by id asc) regardless of the order they were created in;
- each item is a dict with keys ``data``, ``peso``, ``massa_magra``,
  ``gordura_pct`` and ``imc``;
- ``peso``, ``massa_magra`` and ``gordura_pct`` are the raw stored value
  (Decimal) or None when NULL -- never converted to 0;
- ``imc`` is computed on demand from peso and altura (never read from a
  column), and is None when either peso or altura is missing;
- an Aluno with no Avaliacoes gets an empty list ``[]``.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from decimal import Decimal
from pathlib import Path

import pytest

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.avaliacoes.service import avaliacao_series, create_avaliacao
from kairos.migrations_runner import run_migrations


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    run_migrations()
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


@pytest.fixture
def aluno_id(data_dir: Path) -> int:
    """Create a supporting Aluno and return its id."""
    aluno = create_aluno(name="Maria Silva")
    return aluno["id"]


def test_aluno_without_avaliacoes_returns_empty_list(aluno_id: int) -> None:
    assert avaliacao_series(aluno_id) == []


def test_series_returns_ascending_chronological_order_regardless_of_creation_order(
    aluno_id: int,
) -> None:
    create_avaliacao(aluno_id, data="2026-03-01", peso="71")
    create_avaliacao(aluno_id, data="2026-01-10", peso="70")
    create_avaliacao(aluno_id, data="2026-02-15", peso="72")

    series = avaliacao_series(aluno_id)

    assert [item["data"].isoformat() for item in series] == [
        "2026-01-10",
        "2026-02-15",
        "2026-03-01",
    ]


def test_series_computes_imc_per_point(aluno_id: int) -> None:
    create_avaliacao(aluno_id, data="2026-01-15", peso="80", altura="178")

    series = avaliacao_series(aluno_id)

    assert len(series) == 1
    assert series[0]["imc"] == Decimal("25.2")


def test_series_leaves_null_metric_as_none_not_zero(aluno_id: int) -> None:
    create_avaliacao(aluno_id, data="2026-01-15", peso="70")

    series = avaliacao_series(aluno_id)

    assert len(series) == 1
    assert series[0]["peso"] == Decimal("70")
    assert series[0]["gordura_pct"] is None
    assert series[0]["massa_magra"] is None


def test_series_imc_is_none_when_altura_is_missing(aluno_id: int) -> None:
    create_avaliacao(aluno_id, data="2026-01-15", peso="70")

    series = avaliacao_series(aluno_id)

    assert len(series) == 1
    assert series[0]["imc"] is None


def test_series_item_has_expected_keys(aluno_id: int) -> None:
    create_avaliacao(
        aluno_id,
        data="2026-01-15",
        peso="80",
        altura="178",
        gordura_pct="20",
        massa_magra="60",
    )

    series = avaliacao_series(aluno_id)

    assert len(series) == 1
    assert set(series[0].keys()) == {
        "data",
        "peso",
        "massa_magra",
        "gordura_pct",
        "imc",
    }
