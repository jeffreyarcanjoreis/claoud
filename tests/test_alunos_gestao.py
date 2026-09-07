"""Tests for issue 24: the "alunos" (students) service layer's archive /
reactivate / delete operations and the history guard that protects a
student's data from being silently lost.

Covers the functional specification:
- set_status changes an Aluno's status and returns the updated dict;
- set_status with an invalid status raises ValidationError, nothing changed;
- set_status for a non-existent id returns None;
- arquivar_aluno sets status to "inactive"; reativar_aluno sets it back to
  "active";
- aluno_tem_historico is False for a freshly created Aluno and True once a
  single dependent row exists in another domain (a payment, here);
- excluir_aluno returns "ok" and actually deletes the row when the Aluno has
  no history; "tem_historico" and leaves the row untouched when it does;
  "nao_encontrado" for a non-existent id.

Same isolation pattern as the other service suites: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on setup/teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import (
    ValidationError,
    aluno_tem_historico,
    arquivar_aluno,
    create_aluno,
    excluir_aluno,
    get_aluno,
    reativar_aluno,
    set_status,
)
from kairos.financeiro.service import registrar_pagamento
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# set_status / arquivar_aluno / reativar_aluno
# ---------------------------------------------------------------------------


def test_set_status_updates_status_and_returns_the_updated_aluno(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        result = set_status(aluno["id"], "inactive")

    assert result is not None
    assert result["status"] == "inactive"


def test_set_status_with_invalid_status_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            set_status(aluno["id"], "xpto")

        loaded = get_aluno(aluno["id"])

    assert loaded is not None
    assert loaded["status"] == "active"


def test_set_status_for_unknown_id_returns_none(data_dir: Path) -> None:
    with TestClient(app):
        result = set_status(9999, "inactive")

    assert result is None


def test_arquivar_aluno_sets_status_to_inactive(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        result = arquivar_aluno(aluno["id"])

    assert result is not None
    assert result["status"] == "inactive"


def test_reativar_aluno_sets_status_back_to_active(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")
        arquivar_aluno(aluno["id"])

        result = reativar_aluno(aluno["id"])

    assert result is not None
    assert result["status"] == "active"


def test_arquivar_aluno_for_unknown_id_returns_none(data_dir: Path) -> None:
    with TestClient(app):
        result = arquivar_aluno(9999)

    assert result is None


def test_reativar_aluno_for_unknown_id_returns_none(data_dir: Path) -> None:
    with TestClient(app):
        result = reativar_aluno(9999)

    assert result is None


# ---------------------------------------------------------------------------
# aluno_tem_historico
# ---------------------------------------------------------------------------


def test_aluno_tem_historico_is_false_for_a_freshly_created_aluno(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        result = aluno_tem_historico(aluno["id"])

    assert result is False


def test_aluno_tem_historico_is_true_after_a_dependent_row_exists(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")
        registrar_pagamento(aluno["id"], ano=2026, mes=1, valor="100")

        result = aluno_tem_historico(aluno["id"])

    assert result is True


# ---------------------------------------------------------------------------
# excluir_aluno
# ---------------------------------------------------------------------------


def test_excluir_aluno_without_history_deletes_the_row(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        resultado = excluir_aluno(aluno["id"])

        loaded = get_aluno(aluno["id"])

    assert resultado == "ok"
    assert loaded is None


def test_excluir_aluno_with_history_refuses_and_keeps_the_aluno(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")
        registrar_pagamento(aluno["id"], ano=2026, mes=1, valor="100")

        resultado = excluir_aluno(aluno["id"])

        loaded = get_aluno(aluno["id"])

    assert resultado == "tem_historico"
    assert loaded is not None
    assert loaded["id"] == aluno["id"]


def test_excluir_aluno_for_unknown_id_returns_nao_encontrado(
    data_dir: Path,
) -> None:
    with TestClient(app):
        resultado = excluir_aluno(9999)

    assert resultado == "nao_encontrado"
