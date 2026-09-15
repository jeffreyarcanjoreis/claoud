"""Tests for issue 07: plan period validation (validação do período do plano).

Covers the functional specification:
- create_aluno / update_aluno: when both plan_start and plan_end are present
  and plan_end < plan_start, both flows return 400 with "Término do plano
  não pode ser anterior ao início." and nothing is persisted/changed;
- equal dates (plan_start == plan_end) are valid;
- only plan_start present (no plan_end) is valid.

Same isolation pattern as tests/test_cadastro_aluno.py: KAIROS_DATA_DIR
points at a temp dir and the cached engine is disposed on teardown.
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


_ERROR_MESSAGE = "Término do plano não pode ser anterior ao início."


def test_create_with_plan_end_before_plan_start_returns_400_persists_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={
                "name": "Maria Silva",
                "plan_start": "2024-02-15",
                "plan_end": "2024-01-02",
            },
        )

    assert response.status_code == 400
    assert _ERROR_MESSAGE in response.text
    assert _alunos_rows(data_dir) == []


def test_update_with_plan_end_before_plan_start_returns_400_does_not_change_student(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        client.post(
            "/alunos",
            data={
                "name": "Maria Silva",
                "plan_start": "2024-01-02",
                "plan_end": "2024-02-15",
            },
            follow_redirects=False,
        )

        response = client.post(
            "/alunos/1",
            data={
                "name": "Maria Silva",
                "plan_start": "2024-02-15",
                "plan_end": "2024-01-02",
            },
        )

    assert response.status_code == 400
    assert _ERROR_MESSAGE in response.text

    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["plan_start"] == "2024-01-02"
    assert rows[0]["plan_end"] == "2024-02-15"


def test_create_with_equal_plan_dates_is_accepted(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={
                "name": "Maria Silva",
                "plan_start": "2024-01-02",
                "plan_end": "2024-01-02",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["plan_start"] == "2024-01-02"
    assert rows[0]["plan_end"] == "2024-01-02"


def test_update_with_equal_plan_dates_is_accepted(data_dir: Path) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data={"name": "Maria Silva"}, follow_redirects=False)

        response = client.post(
            "/alunos/1",
            data={
                "name": "Maria Silva",
                "plan_start": "2024-03-10",
                "plan_end": "2024-03-10",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["plan_start"] == "2024-03-10"
    assert rows[0]["plan_end"] == "2024-03-10"


def test_create_with_only_plan_start_is_accepted(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={"name": "Maria Silva", "plan_start": "2024-01-02"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["plan_start"] == "2024-01-02"
    assert rows[0]["plan_end"] is None


def test_update_with_only_plan_start_is_accepted(data_dir: Path) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data={"name": "Maria Silva"}, follow_redirects=False)

        response = client.post(
            "/alunos/1",
            data={"name": "Maria Silva", "plan_start": "2024-05-20"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["plan_start"] == "2024-05-20"
    assert rows[0]["plan_end"] is None
