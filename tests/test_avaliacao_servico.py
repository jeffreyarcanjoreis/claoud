"""Tests for issue 02: Avaliacao service (business rules).

Covers the functional specification:
- ``create_avaliacao`` receives raw form values (strings or None), validates
  them and persists through ``session_scope``, returning the saved dict of
  primitives;
- data (date) is required: missing or invalid raises ``ValidationError`` and
  nothing is persisted;
- metrics accept comma or dot as the decimal separator ("72,5" == "72.5"),
  reject non-numeric and negative values (raising ``ValidationError``), and
  treat an empty string as None (NULL) -- rule 6, empty never becomes a fake
  default;
- "0" is a valid metric value (not empty, not negative);
- ``list_avaliacoes(aluno_id)`` returns the Aluno's assessments in reverse
  chronological order (data desc, tie-broken by id desc);
- ``get_avaliacao(avaliacao_id)`` returns the dict for an existing id, or
  None when the id does not exist.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from decimal import Decimal
from pathlib import Path

import pytest

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.avaliacoes.service import (
    ValidationError,
    create_avaliacao,
    get_avaliacao,
    list_avaliacoes,
)
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


def test_create_avaliacao_with_valid_data_and_metrics_saves_and_returns_dict(
    aluno_id: int,
) -> None:
    result = create_avaliacao(
        aluno_id,
        data="2026-01-15",
        peso="72,5",
        altura="168.50",
        gordura_pct="24.7",
        massa_magra="54.10",
        massa_gorda="18.25",
    )

    assert result["aluno_id"] == aluno_id
    assert result["data"].isoformat() == "2026-01-15"
    assert result["peso"] == Decimal("72.5")
    assert result["altura"] == Decimal("168.50")
    assert result["gordura_pct"] == Decimal("24.7")
    assert result["massa_magra"] == Decimal("54.10")
    assert result["massa_gorda"] == Decimal("18.25")
    assert result["id"] is not None
    assert result["created_at"] is not None

    saved = list_avaliacoes(aluno_id)
    assert len(saved) == 1
    assert saved[0]["id"] == result["id"]
    assert saved[0]["peso"] == Decimal("72.5")


def test_create_avaliacao_without_date_raises_validation_error_and_saves_nothing(
    aluno_id: int,
) -> None:
    with pytest.raises(ValidationError):
        create_avaliacao(aluno_id, data=None, peso="70")

    with pytest.raises(ValidationError):
        create_avaliacao(aluno_id, data="", peso="70")

    assert list_avaliacoes(aluno_id) == []


def test_create_avaliacao_with_invalid_date_raises_validation_error(
    aluno_id: int,
) -> None:
    with pytest.raises(ValidationError):
        create_avaliacao(aluno_id, data="2026-13-40", peso="70")

    assert list_avaliacoes(aluno_id) == []


def test_create_avaliacao_with_non_numeric_metric_raises_validation_error_and_saves_nothing(
    aluno_id: int,
) -> None:
    with pytest.raises(ValidationError):
        create_avaliacao(aluno_id, data="2026-01-15", peso="abc")

    assert list_avaliacoes(aluno_id) == []


def test_create_avaliacao_with_negative_metric_raises_validation_error(
    aluno_id: int,
) -> None:
    with pytest.raises(ValidationError):
        create_avaliacao(aluno_id, data="2026-01-15", peso="-5")

    assert list_avaliacoes(aluno_id) == []


def test_create_avaliacao_with_empty_metric_becomes_none(aluno_id: int) -> None:
    result = create_avaliacao(aluno_id, data="2026-01-15", peso="")

    assert result["peso"] is None

    saved = list_avaliacoes(aluno_id)
    assert saved[0]["peso"] is None


def test_create_avaliacao_with_zero_metric_is_accepted(aluno_id: int) -> None:
    result = create_avaliacao(aluno_id, data="2026-01-15", peso="0")

    assert result["peso"] == Decimal("0")


def test_list_avaliacoes_returns_reverse_chronological_order(aluno_id: int) -> None:
    create_avaliacao(aluno_id, data="2026-01-10", peso="70")
    create_avaliacao(aluno_id, data="2026-03-01", peso="71")
    create_avaliacao(aluno_id, data="2026-02-15", peso="72")

    saved = list_avaliacoes(aluno_id)

    assert [item["data"].isoformat() for item in saved] == [
        "2026-03-01",
        "2026-02-15",
        "2026-01-10",
    ]


def test_get_avaliacao_returns_dict_for_existing_id(aluno_id: int) -> None:
    created = create_avaliacao(aluno_id, data="2026-01-15", peso="70")

    result = get_avaliacao(created["id"])

    assert result is not None
    assert result["id"] == created["id"]
    assert result["aluno_id"] == aluno_id
    assert result["peso"] == Decimal("70")


def test_get_avaliacao_returns_none_for_nonexistent_id(aluno_id: int) -> None:
    assert get_avaliacao(999999) is None
