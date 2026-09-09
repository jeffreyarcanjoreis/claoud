"""Tests for issue 02: student registration (cadastro de aluno).

Covers the functional specification:
- GET /alunos/novo renders the "Novo aluno" form (200, Portuguese labels);
- POST /alunos with a name creates the student and redirects (303) to
  /alunos?criado=..., and the list page then shows the success message;
- POST /alunos without a name (empty or whitespace-only) returns 400,
  persists nothing, shows "Nome é obrigatório." and preserves the other
  typed values;
- optional fields sent empty are stored as NULL, never as empty strings;
- a malformed date returns 400 with a clear message and persists nothing;
- status defaults to "active" when missing/empty and an unknown status is
  rejected with 400 and nothing persisted.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows. TestClient is used as a context
manager so the lifespan runs the migrations.
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

import kairos.db
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def _alunos_rows(data_dir: Path) -> List[Dict[str, Any]]:
    """Read every row of the alunos table straight from the SQLite file."""
    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                sa.text("SELECT * FROM alunos ORDER BY id")
            ).mappings().all()
        return [dict(row) for row in rows]
    finally:
        engine.dispose()


def test_get_novo_aluno_form_returns_200_with_form(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/novo")

    assert response.status_code == 200
    assert "<form" in response.text
    assert "Nome" in response.text
    assert "Novo aluno" in response.text


def test_post_with_name_redirects_303_and_persists_student(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={"name": "Maria Silva"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/alunos?criado=")

    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["name"] == "Maria Silva"


def test_following_redirect_shows_success_message(data_dir: Path) -> None:
    """The success message now appears on the list page (/alunos?criado=...)."""
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={"name": "Maria Silva"},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert "/alunos?criado=" in str(response.url)  # landed on the list page
    assert "cadastrado" in response.text


def test_post_without_name_returns_400_preserves_values(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={"name": "", "objective": "Hipertrofia geral"},
        )

    assert response.status_code == 400
    assert "Nome é obrigatório." in response.text
    assert "Hipertrofia geral" in response.text  # typed values are preserved
    assert _alunos_rows(data_dir) == []


def test_post_with_whitespace_only_name_returns_400(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/alunos", data={"name": "   "})

    assert response.status_code == 400
    assert "Nome é obrigatório." in response.text
    assert _alunos_rows(data_dir) == []


def test_empty_optional_fields_are_stored_as_null(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={
                "name": "Maria Silva",
                "birth_date": "",
                "objective": "",
                "phase": "",
                "plan_start": "",
                "plan_end": "",
                "restrictions": "",
                "alert": "",
                "notes": "",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303

    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    row = rows[0]
    for column in (
        "birth_date",
        "objective",
        "phase",
        "plan_start",
        "plan_end",
        "restrictions",
        "alert",
        "notes",
    ):
        assert row[column] is None, f"{column} should be NULL, got {row[column]!r}"


def test_invalid_birth_date_returns_400_and_persists_nothing(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={"name": "Maria Silva", "birth_date": "not-a-date"},
        )

    assert response.status_code == 400
    assert "Data de nascimento inválida." in response.text
    assert _alunos_rows(data_dir) == []


def test_missing_or_empty_status_defaults_to_active(data_dir: Path) -> None:
    with TestClient(app) as client:
        # No status field at all.
        first = client.post(
            "/alunos", data={"name": "Sem Status"}, follow_redirects=False
        )
        # Status sent but empty.
        second = client.post(
            "/alunos",
            data={"name": "Status Vazio", "status": ""},
            follow_redirects=False,
        )

    assert first.status_code == 303
    assert second.status_code == 303

    rows = _alunos_rows(data_dir)
    assert len(rows) == 2
    assert all(row["status"] == "active" for row in rows)


def test_invalid_status_returns_400_and_persists_nothing(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={"name": "Maria Silva", "status": "banido"},
        )

    assert response.status_code == 400
    assert "Status inválido." in response.text
    assert _alunos_rows(data_dir) == []
