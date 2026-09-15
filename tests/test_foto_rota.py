"""Tests for the route that serves a student's photo (issue 03-foto-rota-servir).

Covers the functional specification:
- GET /alunos/{aluno_id}/foto serves the stored photo file with the correct
  content-type (png -> image/png) and body bytes, when the student has a
  photo and the file exists on disk;
- 404 (never 500) when the student exists but has no photo (foto is NULL);
- 404 when the student does not exist;
- 404 when "foto" points to a filename that is no longer on disk (orphan).

Same isolation pattern as tests/test_foto_servico.py and
tests/test_perfil_aluno.py: KAIROS_DATA_DIR points at a temp dir, the cached
SQLAlchemy engine is disposed on teardown, and TestClient is used as a
context manager so the app's startup (migrations) runs.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.config
import kairos.db
from kairos.alunos.fotos import save_foto
from kairos.alunos.service import create_aluno, set_aluno_foto
from kairos.main import app

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_get_foto_of_student_with_photo_returns_200_with_bytes_and_content_type(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        nome = save_foto(PNG_BYTES, "image/png", "x.png")
        set_aluno_foto(aluno["id"], nome)

        response = client.get(f"/alunos/{aluno['id']}/foto")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == PNG_BYTES


def test_get_foto_of_student_without_photo_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Joao Souza")

        response = client.get(f"/alunos/{aluno['id']}/foto")

    assert response.status_code == 404


def test_get_foto_of_nonexistent_student_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999/foto")

    assert response.status_code == 404


def test_get_foto_with_orphaned_file_returns_404_not_500(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Costa")
        nome = save_foto(PNG_BYTES, "image/png", "x.png")
        set_aluno_foto(aluno["id"], nome)
        (kairos.config.fotos_dir() / nome).unlink()

        response = client.get(f"/alunos/{aluno['id']}/foto")

    assert response.status_code == 404
