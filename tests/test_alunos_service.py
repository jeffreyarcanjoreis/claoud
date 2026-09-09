"""Tests for issue 23: the "alunos" (students) service layer's expanded
profile fields (contact, sex, age_reported, weekly_frequency,
conditioning_level, health_conditions, medications).

Covers the functional specification:
- create_aluno accepts and persists the new fields;
- sex/conditioning_level/weekly_frequency outside their fixed option sets
  raise ValidationError (nothing persisted);
- age_reported outside 1..120 (inclusive), or non-numeric, raises
  ValidationError; a valid integer round-trips;
- empty optional fields normalize to None, never a fake default;
- update_aluno accepts and persists the same new fields, with the same
  validation rules, and replaces the previous values (total replacement,
  not a partial patch);
- _to_dict (surfaced through create_aluno/update_aluno/get_aluno) carries
  sex_label, weekly_frequency_label and conditioning_label, each derived
  from the coded value and None when the underlying field is None.

Same isolation pattern as the other service suites: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import (
    CONDITIONING_LEVELS,
    SEX_OPCOES,
    WEEKLY_FREQUENCIES,
    ValidationError,
    create_aluno,
    get_aluno,
    update_aluno,
)
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


_FULL_EXPANDED_PROFILE = {
    "name": "Maria Silva",
    "contact": "(11) 99999-0000",
    "sex": "feminino",
    "age_reported": "34",
    "weekly_frequency": "3-4",
    "conditioning_level": "iniciante",
    "health_conditions": "Hipertensão controlada",
    "medications": "Losartana",
}


# ---------------------------------------------------------------------------
# create_aluno
# ---------------------------------------------------------------------------


def test_create_aluno_persists_the_expanded_profile_fields(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(**_FULL_EXPANDED_PROFILE)

    assert aluno["contact"] == "(11) 99999-0000"
    assert aluno["sex"] == "feminino"
    assert aluno["age_reported"] == 34
    assert aluno["weekly_frequency"] == "3-4"
    assert aluno["conditioning_level"] == "iniciante"
    assert aluno["health_conditions"] == "Hipertensão controlada"
    assert aluno["medications"] == "Losartana"


def test_create_aluno_with_empty_expanded_fields_saves_none(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(
            name="Maria Silva",
            contact="",
            sex="",
            age_reported="",
            weekly_frequency="",
            conditioning_level="",
            health_conditions="",
            medications="",
        )

    assert aluno["contact"] is None
    assert aluno["sex"] is None
    assert aluno["age_reported"] is None
    assert aluno["weekly_frequency"] is None
    assert aluno["conditioning_level"] is None
    assert aluno["health_conditions"] is None
    assert aluno["medications"] is None


def test_create_aluno_with_invalid_sex_raises_validation_error(data_dir: Path) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_aluno(name="Maria Silva", sex="xpto")


def test_create_aluno_with_invalid_conditioning_level_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_aluno(name="Maria Silva", conditioning_level="xpto")


def test_create_aluno_with_invalid_weekly_frequency_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_aluno(name="Maria Silva", weekly_frequency="xpto")


def test_create_aluno_with_age_reported_out_of_range_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_aluno(name="Maria Silva", age_reported="0")

        with pytest.raises(ValidationError):
            create_aluno(name="Maria Silva", age_reported="121")


def test_create_aluno_with_non_numeric_age_reported_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_aluno(name="Maria Silva", age_reported="abc")


def test_create_aluno_accepts_the_boundary_ages(data_dir: Path) -> None:
    with TestClient(app):
        low = create_aluno(name="Idade Mínima", age_reported="1")
        high = create_aluno(name="Idade Máxima", age_reported="120")

    assert low["age_reported"] == 1
    assert high["age_reported"] == 120


def test_create_aluno_with_invalid_data_persists_nothing(data_dir: Path) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_aluno(name="Nao Deveria Existir", sex="xpto")

        from kairos.alunos.service import list_alunos

        assert list_alunos() == []


# ---------------------------------------------------------------------------
# update_aluno
# ---------------------------------------------------------------------------


def test_update_aluno_replaces_the_expanded_profile_fields(data_dir: Path) -> None:
    with TestClient(app):
        created = create_aluno(**_FULL_EXPANDED_PROFILE)

        updated = update_aluno(
            created["id"],
            name="Maria Silva",
            contact="maria@example.com",
            sex="outro",
            age_reported="40",
            weekly_frequency="5+",
            conditioning_level="avancado",
            health_conditions="Nenhuma",
            medications="Nenhum",
        )

    assert updated is not None
    assert updated["contact"] == "maria@example.com"
    assert updated["sex"] == "outro"
    assert updated["age_reported"] == 40
    assert updated["weekly_frequency"] == "5+"
    assert updated["conditioning_level"] == "avancado"
    assert updated["health_conditions"] == "Nenhuma"
    assert updated["medications"] == "Nenhum"


def test_update_aluno_with_empty_expanded_fields_clears_them_to_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        created = create_aluno(**_FULL_EXPANDED_PROFILE)

        updated = update_aluno(
            created["id"],
            name="Maria Silva",
            contact="",
            sex="",
            age_reported="",
            weekly_frequency="",
            conditioning_level="",
            health_conditions="",
            medications="",
        )

    assert updated is not None
    assert updated["contact"] is None
    assert updated["sex"] is None
    assert updated["age_reported"] is None
    assert updated["weekly_frequency"] is None
    assert updated["conditioning_level"] is None
    assert updated["health_conditions"] is None
    assert updated["medications"] is None


def test_update_aluno_with_invalid_sex_raises_validation_error(data_dir: Path) -> None:
    with TestClient(app):
        created = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            update_aluno(created["id"], name="Maria Silva", sex="xpto")


def test_update_aluno_with_age_reported_out_of_range_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        created = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            update_aluno(created["id"], name="Maria Silva", age_reported="121")


def test_update_aluno_unknown_id_returns_none(data_dir: Path) -> None:
    with TestClient(app):
        result = update_aluno(9999, name="Alguém")

    assert result is None


# ---------------------------------------------------------------------------
# _to_dict labels, surfaced by create_aluno/update_aluno/get_aluno
# ---------------------------------------------------------------------------


def test_to_dict_labels_reflect_the_coded_values(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(**_FULL_EXPANDED_PROFILE)

        loaded = get_aluno(aluno["id"])

    assert loaded is not None
    assert loaded["sex_label"] == "Feminino"
    assert loaded["weekly_frequency_label"] == "3 a 4 dias"
    assert loaded["conditioning_label"] == "Iniciante"


def test_to_dict_labels_are_none_when_coded_fields_are_none(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        loaded = get_aluno(aluno["id"])

    assert loaded is not None
    assert loaded["sex_label"] is None
    assert loaded["weekly_frequency_label"] is None
    assert loaded["conditioning_label"] is None
    assert loaded["contact"] is None
    assert loaded["age_reported"] is None
    assert loaded["health_conditions"] is None
    assert loaded["medications"] is None


def test_every_sex_opcao_is_accepted_and_labeled(data_dir: Path) -> None:
    with TestClient(app):
        for value in SEX_OPCOES:
            aluno = create_aluno(name=f"Aluno {value}", sex=value)
            assert aluno["sex"] == value
            assert aluno["sex_label"] is not None


def test_every_conditioning_level_is_accepted_and_labeled(data_dir: Path) -> None:
    with TestClient(app):
        for value in CONDITIONING_LEVELS:
            aluno = create_aluno(name=f"Aluno {value}", conditioning_level=value)
            assert aluno["conditioning_level"] == value
            assert aluno["conditioning_label"] is not None


def test_every_weekly_frequency_is_accepted_and_labeled(data_dir: Path) -> None:
    with TestClient(app):
        for value in WEEKLY_FREQUENCIES:
            aluno = create_aluno(name=f"Aluno {value}", weekly_frequency=value)
            assert aluno["weekly_frequency"] == value
            assert aluno["weekly_frequency_label"] is not None
