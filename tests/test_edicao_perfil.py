"""Tests for issues 06 (edição do perfil) and 08 (status ativo/inativo).

Covers the functional specification:
- GET /alunos/{id}/editar shows the form pre-filled with current values,
  with date fields rendered in ISO "YYYY-MM-DD" (what a type=date input
  expects);
- POST /alunos/{id} saves via the same normalization/validation as the
  create flow and redirects 303 to /alunos/{id}?atualizado=1; following the
  redirect shows "Perfil atualizado." and the new value; the list also
  reflects the new value;
- a validation error (e.g. empty name) returns 400, re-rendering the form
  with the typed values preserved and nothing changed in the database;
- an unknown id returns 404 for both GET .../editar and POST;
- (issue 08) editing the status to "inactive" keeps the student in the list
  with the "Inativo" badge; editing back to "active" shows "Ativo" again.

Same isolation pattern as tests/test_lista_alunos.py and
tests/test_perfil_aluno.py: KAIROS_DATA_DIR points at a temp dir and the
cached engine is disposed on teardown.
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


_FULL_PROFILE = {
    "name": "Maria Silva",
    "birth_date": "1990-03-15",
    "objective": "Hipertrofia geral",
    "phase": "Adaptação",
    "plan_start": "2024-01-02",
    "plan_end": "2024-02-15",
    "restrictions": "Condromalácia patelar",
    "alert": "Evitar impacto no joelho",
    "notes": "Prefere treinar de manhã",
}


def test_edit_form_shows_current_values_prefilled(data_dir: Path) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data=_FULL_PROFILE, follow_redirects=False)
        response = client.get("/alunos/1/editar")

    assert response.status_code == 200
    assert 'value="Hipertrofia geral"' in response.text or "Hipertrofia geral" in response.text
    # Dates must be in ISO format for the date inputs.
    assert 'value="1990-03-15"' in response.text
    assert 'value="2024-01-02"' in response.text
    assert 'value="2024-02-15"' in response.text
    assert "15/03/1990" not in response.text


def test_post_update_changes_field_redirects_and_reflects_everywhere(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data=_FULL_PROFILE, follow_redirects=False)

        updated = dict(_FULL_PROFILE)
        updated["objective"] = "Emagrecimento"

        response = client.post("/alunos/1", data=updated, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/alunos/1?atualizado=1"

        profile = client.get(response.headers["location"])
        assert profile.status_code == 200
        assert "Perfil atualizado." in profile.text
        assert "Emagrecimento" in profile.text
        assert "Hipertrofia geral" not in profile.text

        lista = client.get("/alunos")
        assert "Emagrecimento" in lista.text
        assert "Hipertrofia geral" not in lista.text

    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    assert rows[0]["objective"] == "Emagrecimento"


def test_post_update_with_empty_name_returns_400_preserves_values_and_data(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data=_FULL_PROFILE, follow_redirects=False)

        attempt = dict(_FULL_PROFILE)
        attempt["name"] = ""
        attempt["objective"] = "Nunca deveria ser salvo"

        response = client.post("/alunos/1", data=attempt)

    assert response.status_code == 400
    assert "Nome é obrigatório." in response.text
    # Typed values (other than the invalid one) are preserved in the form.
    assert "Nunca deveria ser salvo" in response.text

    rows = _alunos_rows(data_dir)
    assert len(rows) == 1
    # Nothing was actually changed in the database.
    assert rows[0]["name"] == "Maria Silva"
    assert rows[0]["objective"] == "Hipertrofia geral"


def test_get_edit_form_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999/editar")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_post_update_unknown_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/alunos/999", data={"name": "Alguém"})

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_editing_status_to_inactive_keeps_student_in_list_with_badge(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data={"name": "Maria Silva"}, follow_redirects=False)

        inactive = {"name": "Maria Silva", "status": "inactive"}
        response = client.post("/alunos/1", data=inactive, follow_redirects=False)
        assert response.status_code == 303

        lista = client.get("/alunos")
        assert "Maria Silva" in lista.text
        assert "Inativo" in lista.text

        active_again = {"name": "Maria Silva", "status": "active"}
        response = client.post("/alunos/1", data=active_again, follow_redirects=False)
        assert response.status_code == 303

        lista = client.get("/alunos")
        assert "Maria Silva" in lista.text
        assert "Ativo" in lista.text
