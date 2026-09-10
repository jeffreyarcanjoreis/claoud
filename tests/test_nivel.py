"""Tests for the "nivel" (student self-recognized level) domain -- issue 02.

Covers the functional specification for the service layer
(``kairos.nivel.service``); this issue is data + service only, with no
routes/UI:

- ``reconhecer`` persists a new self-recognition and returns it with
  ``nivel_label``/``nivel_descricao`` resolved from the recognized level;
- this is never an upsert: recognizing a level twice for the same aluno
  creates two separate history rows;
- validation: an invalid ``nivel`` (outside ``NIVEL_OPCOES``) is rejected
  and nothing is persisted;
- ``nota`` normalization: empty/whitespace-only becomes ``None``, and a
  value with surrounding whitespace is stripped;
- ``nivel_atual`` returns the most recently recognized level (tie-broken by
  id descending, since ``created_at`` may share the same instant for
  writes in quick succession), or ``None`` when the aluno has no
  recognition yet;
- ``list_reconhecimentos`` returns the full history, most recent first, and
  an empty list when there is none;
- isolation: one aluno's recognitions never leak into another aluno's
  history.

Isolation: KAIROS_DATA_DIR points at a temp dir and the cached engine is
disposed on setup/teardown (same pattern as tests/test_registro_treino.py);
the suite-wide ``_no_remote_database_url`` autouse fixture (see
tests/conftest.py) already keeps KAIROS_DATABASE_URL out of the picture.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.nivel.service import (
    NIVEL_DESCRICOES,
    NIVEL_LABELS,
    NIVEL_OPCOES,
    ValidationError,
    list_reconhecimentos,
    nivel_atual,
    reconhecer,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# 1. Service: reconhecer persists and resolves label/descricao
# ---------------------------------------------------------------------------


def test_reconhecer_persists_and_resolves_label_and_descricao(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        criado = reconhecer(aluno["id"], nivel="construcao")

    assert criado["aluno_id"] == aluno["id"]
    assert criado["nivel"] == "construcao"
    assert criado["nivel_label"] == "II · Construção"
    assert criado["nivel_label"] == NIVEL_LABELS["construcao"]
    assert criado["nivel_descricao"] == NIVEL_DESCRICOES["construcao"]
    assert criado["nivel_descricao"] is not None
    assert criado["nota"] is None
    assert criado["id"] is not None
    assert criado["created_at"] is not None


# ---------------------------------------------------------------------------
# 2. Service: NOT an upsert -- history is preserved
# ---------------------------------------------------------------------------


def test_reconhecer_twice_creates_two_history_entries(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        reconhecer(aluno["id"], nivel="fundacao")
        reconhecer(aluno["id"], nivel="construcao")

        historico = list_reconhecimentos(aluno["id"])

    assert len(historico) == 2
    assert {r["nivel"] for r in historico} == {"fundacao", "construcao"}


def test_reconhecer_same_level_twice_still_creates_two_entries(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        reconhecer(aluno["id"], nivel="dominio")
        reconhecer(aluno["id"], nivel="dominio")

        historico = list_reconhecimentos(aluno["id"])

    assert len(historico) == 2
    assert all(r["nivel"] == "dominio" for r in historico)


# ---------------------------------------------------------------------------
# 3. Service: validation -- invalid nivel is rejected, nothing persisted
# ---------------------------------------------------------------------------


def test_reconhecer_rejects_invalid_nivel_option(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        with pytest.raises(ValidationError, match="Nível inválido"):
            reconhecer(aluno["id"], nivel="xpto")

        assert list_reconhecimentos(aluno["id"]) == []


@pytest.mark.parametrize("nivel_valido", NIVEL_OPCOES)
def test_reconhecer_accepts_every_documented_nivel_option(
    data_dir: Path, nivel_valido: str
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        criado = reconhecer(aluno["id"], nivel=nivel_valido)

    assert criado["nivel"] == nivel_valido
    assert criado["nivel_label"] == NIVEL_LABELS[nivel_valido]
    assert criado["nivel_descricao"] == NIVEL_DESCRICOES[nivel_valido]


# ---------------------------------------------------------------------------
# 4. Service: nota normalization (empty means NULL, whitespace stripped)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nota_vazia", ["", "   "])
def test_reconhecer_with_blank_nota_stores_none(
    data_dir: Path, nota_vazia: str
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        criado = reconhecer(aluno["id"], nivel="fundacao", nota=nota_vazia)

    assert criado["nota"] is None


def test_reconhecer_strips_surrounding_whitespace_from_nota(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        criado = reconhecer(
            aluno["id"], nivel="fundacao", nota="  Me sinto mais confiante.  "
        )

    assert criado["nota"] == "Me sinto mais confiante."


# ---------------------------------------------------------------------------
# 5. Service: nivel_atual returns the most recent recognition (or None)
# ---------------------------------------------------------------------------


def test_nivel_atual_returns_the_most_recently_recognized_level(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        reconhecer(aluno["id"], nivel="fundacao")
        reconhecer(aluno["id"], nivel="construcao")
        mais_recente = reconhecer(aluno["id"], nivel="dominio")

        atual = nivel_atual(aluno["id"])

    assert atual is not None
    assert atual["id"] == mais_recente["id"]
    assert atual["nivel"] == "dominio"
    assert atual["nivel_label"] == NIVEL_LABELS["dominio"]


def test_nivel_atual_for_aluno_without_recognition_returns_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        atual = nivel_atual(aluno["id"])

    assert atual is None


# ---------------------------------------------------------------------------
# 6. Service: list_reconhecimentos ordering (most recent first) and empty
# ---------------------------------------------------------------------------


def test_list_reconhecimentos_orders_most_recent_first(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        primeiro = reconhecer(aluno["id"], nivel="fundacao")
        segundo = reconhecer(aluno["id"], nivel="construcao")
        terceiro = reconhecer(aluno["id"], nivel="dominio")

        historico = list_reconhecimentos(aluno["id"])

    assert [r["id"] for r in historico] == [
        terceiro["id"],
        segundo["id"],
        primeiro["id"],
    ]
    assert [r["nivel"] for r in historico] == ["dominio", "construcao", "fundacao"]


def test_list_reconhecimentos_for_aluno_without_recognition_is_empty(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Marcos Vieira")

        historico = list_reconhecimentos(aluno["id"])

    assert historico == []


# ---------------------------------------------------------------------------
# 7. Service: isolation between alunos
# ---------------------------------------------------------------------------


def test_reconhecimento_of_one_aluno_does_not_leak_into_another(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno_a = create_aluno(name="Aluno A")
        aluno_b = create_aluno(name="Aluno B")

        reconhecer(aluno_a["id"], nivel="fundacao")
        reconhecer(aluno_b["id"], nivel="maestria")

        historico_a = list_reconhecimentos(aluno_a["id"])
        historico_b = list_reconhecimentos(aluno_b["id"])

    assert len(historico_a) == 1
    assert historico_a[0]["nivel"] == "fundacao"
    assert len(historico_b) == 1
    assert historico_b[0]["nivel"] == "maestria"
    assert nivel_atual(aluno_a["id"])["nivel"] == "fundacao"
    assert nivel_atual(aluno_b["id"])["nivel"] == "maestria"
