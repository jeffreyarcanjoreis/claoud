"""Tests for issue 02: perimetria service (business rules).

Covers the functional specification:
- ``create_avaliacao`` accepts an optional ``perimetria: dict[str, str]``
  (segment key -> raw value); each segment with a filled value becomes a
  ``Perimetria`` row linked to the assessment, with ``segmento`` set to the
  segment's label and ``valor`` parsed as a ``Decimal`` (comma or dot
  accepted, reusing ``_parse_number``);
- an empty segment value does not create a row (rule 6: no data means NULL,
  never a fake zero row);
- keys outside ``PERIMETRIA_SEGMENTOS`` are ignored;
- a negative (or otherwise invalid) perimetria value raises
  ``ValidationError`` and nothing is persisted -- not the perimetria rows,
  and not the Avaliacao itself (atomicity: all validation happens before
  anything is added to the session);
- ``list_perimetria(avaliacao_id)`` returns the assessment's measurements in
  the canonical order of ``PERIMETRIA_SEGMENTOS``, regardless of the order
  the segments were supplied in;
- ``create_avaliacao`` without a ``perimetria`` argument still works and
  ``list_perimetria`` returns an empty list for it.

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
    list_avaliacoes,
    list_perimetria,
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


def test_create_avaliacao_with_two_segments_saves_two_perimetria_rows(
    aluno_id: int,
) -> None:
    result = create_avaliacao(
        aluno_id,
        data="2026-01-15",
        perimetria={"cintura": "82,5", "coxa_d": "58"},
    )

    medidas = list_perimetria(result["id"])

    assert len(medidas) == 2
    assert medidas[0]["segmento"] == "Cintura"
    assert medidas[0]["valor"] == Decimal("82.5")
    assert medidas[1]["segmento"] == "Coxa D"
    assert medidas[1]["valor"] == Decimal("58")


def test_create_avaliacao_with_empty_segment_does_not_create_row(
    aluno_id: int,
) -> None:
    result = create_avaliacao(
        aluno_id,
        data="2026-01-15",
        perimetria={"cintura": "80", "coxa_d": ""},
    )

    medidas = list_perimetria(result["id"])

    assert len(medidas) == 1
    assert medidas[0]["segmento"] == "Cintura"
    assert medidas[0]["valor"] == Decimal("80")


def test_create_avaliacao_with_negative_perimetria_raises_and_saves_nothing(
    aluno_id: int,
) -> None:
    with pytest.raises(ValidationError):
        create_avaliacao(
            aluno_id,
            data="2026-01-15",
            perimetria={"cintura": "-5"},
        )

    # Atomicity: neither the perimetria rows nor the Avaliacao itself were
    # persisted.
    assert list_avaliacoes(aluno_id) == []


def test_create_avaliacao_perimetria_value_accepts_comma_as_decimal(
    aluno_id: int,
) -> None:
    result = create_avaliacao(
        aluno_id,
        data="2026-01-15",
        perimetria={"cintura": "82,5"},
    )

    medidas = list_perimetria(result["id"])

    assert medidas[0]["valor"] == Decimal("82.5")
    assert isinstance(medidas[0]["valor"], Decimal)


def test_list_perimetria_returns_canonical_order_regardless_of_input_order(
    aluno_id: int,
) -> None:
    result = create_avaliacao(
        aluno_id,
        data="2026-01-15",
        perimetria={"coxa_d": "58", "cintura": "82"},
    )

    medidas = list_perimetria(result["id"])

    assert [medida["segmento"] for medida in medidas] == ["Cintura", "Coxa D"]


def test_create_avaliacao_without_perimetria_creates_avaliacao_with_no_measurements(
    aluno_id: int,
) -> None:
    result = create_avaliacao(aluno_id, data="2026-01-15", peso="70")

    assert list_avaliacoes(aluno_id)[0]["id"] == result["id"]
    assert list_perimetria(result["id"]) == []


def test_create_avaliacao_ignores_keys_outside_standard_segments(
    aluno_id: int,
) -> None:
    result = create_avaliacao(
        aluno_id,
        data="2026-01-15",
        perimetria={"inexistente": "50", "cintura": "80"},
    )

    medidas = list_perimetria(result["id"])

    assert len(medidas) == 1
    assert medidas[0]["segmento"] == "Cintura"
    assert medidas[0]["valor"] == Decimal("80")
