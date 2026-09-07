"""Tests for issue 02: Agenda service (business rules).

Covers the functional specification:
- ``create_sessao`` receives raw form values (strings or None), validates
  them before persisting (atomicity: nothing is saved on error), and
  returns the saved dict of primitives;
- data (date) and hora (time) are required: missing or invalid raises
  ``ValidationError`` and nothing is persisted;
- tipo is required and must be one of {"individual", "grupo"};
- duracao_min is optional: empty becomes None; when given must be a
  positive integer, otherwise raises ``ValidationError``;
- observacao is optional: empty becomes None;
- ``list_sessoes(aluno_id)`` returns the Aluno's scheduled sessions in
  chronological (ascending) order (data asc, hora asc, tie-broken by id
  asc);
- ``get_sessao(sessao_id)`` returns the dict for an existing id, or None
  when the id does not exist;
- ``cancel_sessao(sessao_id)`` removes the session and returns True when it
  existed, False when it did not.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

import datetime
from pathlib import Path

import pytest

import kairos.db
from kairos.agenda.service import (
    ValidationError,
    cancel_sessao,
    create_sessao,
    get_sessao,
    list_sessoes,
)
from kairos.alunos.service import create_aluno
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


def test_create_sessao_with_valid_data_saves_and_returns_dict(aluno_id: int) -> None:
    result = create_sessao(
        aluno_id,
        data="2026-09-01",
        hora="09:00",
        tipo="individual",
        duracao_min="60",
    )

    assert result["aluno_id"] == aluno_id
    assert result["data"] == datetime.date(2026, 9, 1)
    assert result["hora"] == datetime.time(9, 0)
    assert result["tipo"] == "individual"
    assert result["duracao_min"] == 60
    assert result["id"] is not None
    assert result["created_at"] is not None

    saved = list_sessoes(aluno_id)
    assert len(saved) == 1
    assert saved[0]["id"] == result["id"]
    assert saved[0]["data"] == datetime.date(2026, 9, 1)
    assert saved[0]["hora"] == datetime.time(9, 0)
    assert saved[0]["tipo"] == "individual"
    assert saved[0]["duracao_min"] == 60


def test_create_sessao_without_date_raises_validation_error_and_saves_nothing(
    aluno_id: int,
) -> None:
    with pytest.raises(ValidationError):
        create_sessao(aluno_id, data=None, hora="09:00", tipo="individual")

    with pytest.raises(ValidationError):
        create_sessao(aluno_id, data="", hora="09:00", tipo="individual")

    assert list_sessoes(aluno_id) == []


def test_create_sessao_without_hora_raises_validation_error_and_saves_nothing(
    aluno_id: int,
) -> None:
    with pytest.raises(ValidationError):
        create_sessao(aluno_id, data="2026-09-01", hora=None, tipo="individual")

    with pytest.raises(ValidationError):
        create_sessao(aluno_id, data="2026-09-01", hora="", tipo="individual")

    assert list_sessoes(aluno_id) == []


def test_create_sessao_with_invalid_date_raises_validation_error(aluno_id: int) -> None:
    with pytest.raises(ValidationError):
        create_sessao(
            aluno_id, data="2026-13-40", hora="09:00", tipo="individual"
        )

    assert list_sessoes(aluno_id) == []


def test_create_sessao_with_invalid_hora_raises_validation_error(aluno_id: int) -> None:
    with pytest.raises(ValidationError):
        create_sessao(
            aluno_id, data="2026-09-01", hora="99:99", tipo="individual"
        )

    assert list_sessoes(aluno_id) == []


def test_create_sessao_with_invalid_tipo_raises_validation_error(aluno_id: int) -> None:
    with pytest.raises(ValidationError):
        create_sessao(aluno_id, data="2026-09-01", hora="09:00", tipo="x")

    with pytest.raises(ValidationError):
        create_sessao(aluno_id, data="2026-09-01", hora="09:00", tipo=None)

    assert list_sessoes(aluno_id) == []


def test_create_sessao_with_zero_or_negative_duracao_raises_validation_error(
    aluno_id: int,
) -> None:
    with pytest.raises(ValidationError):
        create_sessao(
            aluno_id,
            data="2026-09-01",
            hora="09:00",
            tipo="individual",
            duracao_min="0",
        )

    with pytest.raises(ValidationError):
        create_sessao(
            aluno_id,
            data="2026-09-01",
            hora="09:00",
            tipo="individual",
            duracao_min="-5",
        )

    assert list_sessoes(aluno_id) == []


def test_create_sessao_with_non_numeric_duracao_raises_validation_error(
    aluno_id: int,
) -> None:
    with pytest.raises(ValidationError):
        create_sessao(
            aluno_id,
            data="2026-09-01",
            hora="09:00",
            tipo="individual",
            duracao_min="abc",
        )

    assert list_sessoes(aluno_id) == []


def test_create_sessao_with_empty_duracao_becomes_none(aluno_id: int) -> None:
    result = create_sessao(
        aluno_id, data="2026-09-01", hora="09:00", tipo="individual", duracao_min=""
    )

    assert result["duracao_min"] is None

    saved = list_sessoes(aluno_id)
    assert saved[0]["duracao_min"] is None


def test_create_sessao_with_empty_observacao_becomes_none(aluno_id: int) -> None:
    result = create_sessao(
        aluno_id,
        data="2026-09-01",
        hora="09:00",
        tipo="individual",
        observacao="",
    )

    assert result["observacao"] is None

    saved = list_sessoes(aluno_id)
    assert saved[0]["observacao"] is None


def test_list_sessoes_returns_chronological_order(aluno_id: int) -> None:
    create_sessao(aluno_id, data="2026-09-03", hora="08:00", tipo="individual")
    create_sessao(aluno_id, data="2026-09-01", hora="10:00", tipo="individual")
    create_sessao(aluno_id, data="2026-09-01", hora="07:00", tipo="individual")

    saved = list_sessoes(aluno_id)

    assert [(item["data"], item["hora"]) for item in saved] == [
        (datetime.date(2026, 9, 1), datetime.time(7, 0)),
        (datetime.date(2026, 9, 1), datetime.time(10, 0)),
        (datetime.date(2026, 9, 3), datetime.time(8, 0)),
    ]


def test_get_sessao_returns_none_for_nonexistent_id(aluno_id: int) -> None:
    assert get_sessao(999999) is None


def test_get_sessao_returns_dict_for_existing_id(aluno_id: int) -> None:
    created = create_sessao(
        aluno_id, data="2026-09-01", hora="09:00", tipo="individual"
    )

    result = get_sessao(created["id"])

    assert result is not None
    assert result["id"] == created["id"]
    assert result["aluno_id"] == aluno_id
    assert result["data"] == datetime.date(2026, 9, 1)
    assert result["hora"] == datetime.time(9, 0)


def test_cancel_sessao_removes_existing_session_and_returns_true(
    aluno_id: int,
) -> None:
    create_sessao(aluno_id, data="2026-09-01", hora="09:00", tipo="individual")
    sessao_id = list_sessoes(aluno_id)[0]["id"]

    result = cancel_sessao(sessao_id)

    assert result is True
    assert list_sessoes(aluno_id) == []


def test_cancel_sessao_returns_false_for_nonexistent_id(aluno_id: int) -> None:
    assert cancel_sessao(999999) is False
