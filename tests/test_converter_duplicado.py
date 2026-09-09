"""Tests for issue 24: duplicate-student detection when converting a lead
(Contato) into a student (Aluno).

Covers the functional specification:
- at the service layer, converter_contato_em_aluno raises AlunoDuplicado
  (without force) when an Aluno with the same name already exists, and
  creates the Aluno anyway when force=True;
- at the route layer, POST /contatos/{id}/converter without force responds
  200 with a warning about the duplicate, a link to the existing Aluno and a
  "mesmo assim" ("anyway") button carrying a hidden force=1 field — and does
  not create a new Aluno (the total Aluno count is unchanged);
- POST /contatos/{id}/converter with force=1 creates the new Aluno anyway
  and redirects (303) to /alunos/{new_id}.

Same isolation pattern as the other route suites: KAIROS_DATA_DIR points at
a temp dir and the cached engine is disposed on setup/teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno, list_alunos
from kairos.contatos.service import (
    AlunoDuplicado,
    converter_contato_em_aluno,
    create_contato,
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


# ---------------------------------------------------------------------------
# service layer
# ---------------------------------------------------------------------------


def test_converter_contato_em_aluno_raises_aluno_duplicado_without_force(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Fulano")
        lead = create_contato(nome="Fulano")

        with pytest.raises(AlunoDuplicado) as exc_info:
            converter_contato_em_aluno(lead["id"])

    assert exc_info.value.aluno_existente_id == aluno["id"]
    assert exc_info.value.aluno_existente_nome == "Fulano"


def test_converter_contato_em_aluno_with_force_creates_a_second_aluno(
    data_dir: Path,
) -> None:
    with TestClient(app):
        create_aluno(name="Fulano")
        lead = create_contato(nome="Fulano")

        novo_id = converter_contato_em_aluno(lead["id"], force=True)

        alunos = list_alunos()

    assert novo_id is not None
    assert len(alunos) == 2
    assert any(a["id"] == novo_id for a in alunos)


# ---------------------------------------------------------------------------
# route layer
# ---------------------------------------------------------------------------


def test_converter_route_without_force_shows_duplicate_warning(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Fulano")
        lead = create_contato(nome="Fulano")

        response = client.post(
            f"/contatos/{lead['id']}/converter", follow_redirects=False
        )

    assert response.status_code == 200
    body = response.text
    assert f'href="/alunos/{aluno["id"]}"' in body
    assert 'name="force" value="1"' in body
    assert "mesmo assim" in body.lower()


def test_converter_route_without_force_does_not_create_a_new_aluno(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        create_aluno(name="Fulano")
        lead = create_contato(nome="Fulano")

        client.post(f"/contatos/{lead['id']}/converter", follow_redirects=False)

        alunos = list_alunos()

    assert len(alunos) == 1


def test_converter_route_with_force_creates_and_redirects(data_dir: Path) -> None:
    with TestClient(app) as client:
        create_aluno(name="Fulano")
        lead = create_contato(nome="Fulano")

        response = client.post(
            f"/contatos/{lead['id']}/converter",
            data={"force": "1"},
            follow_redirects=False,
        )

        alunos = list_alunos()

    assert response.status_code == 303
    assert response.headers["location"].startswith("/alunos/")
    assert len(alunos) == 2
