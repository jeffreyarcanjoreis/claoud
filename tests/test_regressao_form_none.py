"""Regression tests for the "None" string leaking into optional textareas.

Context: ``kairos/templates/alunos/_form.html`` used to render Python
``None`` values as the literal string "None" inside inputs/textareas. When
the form was re-rendered after a validation error (e.g. an invalid plan
period) with optional fields absent from the submission, the textareas for
restrictions/alert/notes showed "None" instead of being empty. Submitting
that re-rendered form would then persist the literal string "None" in the
database instead of NULL, violating architecture rule 6 ("dados nunca
inventados"). The fix coerces None/absent values to "" in the template.

These tests cover:
- error re-render on the EDIT form does not leak "None" into the optional
  textareas when those fields are absent from the submission;
- error re-render on the CREATE form has the same guarantee;
- a subsequent valid submission with those fields absent still persists
  NULL (not the string "None") in the database;
- a legitimately typed value survives both an error re-render and a
  successful save.

Same isolation pattern as tests/test_cadastro_aluno.py: KAIROS_DATA_DIR
points at a temp dir and the cached engine is disposed on teardown.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def _textarea_content(html: str, field_name: str) -> Optional[str]:
    """Return the raw text between a <textarea name="field_name"> tags.

    Returns None if no textarea with that name is found in the HTML.
    """
    pattern = re.compile(
        r'<textarea[^>]*name="' + re.escape(field_name) + r'"[^>]*>(.*?)</textarea>',
        re.DOTALL,
    )
    match = pattern.search(html)
    return match.group(1) if match else None


_INVALID_PERIOD = {
    "plan_start": "2024-02-15",
    "plan_end": "2024-01-02",
}

_OPTIONAL_TEXTAREA_FIELDS = ("restrictions", "alert", "notes")


def test_edit_error_rerender_with_absent_optional_fields_has_no_literal_none(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data={"name": "Maria Silva"}, follow_redirects=False)

        # Invalid period, and restrictions/alert/notes are not sent at all.
        data = {"name": "Maria Silva", **_INVALID_PERIOD}
        response = client.post("/alunos/1", data=data)

    assert response.status_code == 400
    assert "None" not in response.text
    for field in _OPTIONAL_TEXTAREA_FIELDS:
        content = _textarea_content(response.text, field)
        assert content is not None, f"textarea {field!r} not found in response"
        assert content.strip() == "", f"textarea {field!r} should be empty, got {content!r}"


def test_create_error_rerender_with_absent_optional_fields_has_no_literal_none(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        data = {"name": "Maria Silva", **_INVALID_PERIOD}
        response = client.post("/alunos", data=data)

    assert response.status_code == 400
    assert "None" not in response.text
    for field in _OPTIONAL_TEXTAREA_FIELDS:
        content = _textarea_content(response.text, field)
        assert content is not None, f"textarea {field!r} not found in response"
        assert content.strip() == "", f"textarea {field!r} should be empty, got {content!r}"


def test_update_with_absent_optional_fields_persists_null_not_literal_none(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        client.post(
            "/alunos",
            data={
                "name": "Maria Silva",
                "restrictions": "Condromalácia patelar",
                "alert": "Evitar impacto no joelho",
                "notes": "Prefere treinar de manhã",
            },
            follow_redirects=False,
        )

        # Valid period, restrictions/alert/notes not sent at all.
        response = client.post(
            "/alunos/1",
            data={"name": "Maria Silva", "plan_start": "2024-01-02", "plan_end": "2024-02-15"},
            follow_redirects=False,
        )

    assert response.status_code == 303

    db_file = data_dir / "kairos.db"
    engine = sa.create_engine(f"sqlite:///{db_file.resolve().as_posix()}")
    try:
        with engine.connect() as connection:
            row = connection.execute(
                sa.text(
                    "SELECT restrictions, alert, notes FROM alunos WHERE id = 1"
                )
            ).mappings().one()
    finally:
        engine.dispose()

    assert row["restrictions"] is None
    assert row["alert"] is None
    assert row["notes"] is None

    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["restrictions"] is None
    assert rows[0]["alert"] is None
    assert rows[0]["notes"] is None


def test_legitimate_value_survives_error_rerender_and_successful_save(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data={"name": "Maria Silva"}, follow_redirects=False)

        # First, an invalid submission that still carries a real value for
        # restrictions: it must be preserved in the re-rendered form, not
        # replaced with "None" nor lost.
        invalid_data = {
            "name": "Maria Silva",
            "restrictions": "joelho",
            **_INVALID_PERIOD,
        }
        error_response = client.post("/alunos/1", data=invalid_data)

        assert error_response.status_code == 400
        content = _textarea_content(error_response.text, "restrictions")
        assert content is not None
        assert content.strip() == "joelho"
        assert "None" not in error_response.text

        # Now submit the same value with a valid period: it must be saved
        # as-is.
        valid_data = {
            "name": "Maria Silva",
            "restrictions": "joelho",
            "plan_start": "2024-01-02",
            "plan_end": "2024-02-15",
        }
        success_response = client.post("/alunos/1", data=valid_data, follow_redirects=False)
        assert success_response.status_code == 303

    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["restrictions"] == "joelho"
