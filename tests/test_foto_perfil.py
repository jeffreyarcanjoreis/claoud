"""Tests for the photo/placeholder shown on the student profile header
(issue 05-foto-perfil-placeholder).

Covers the functional specification:
- When the aluno has no photo, the shared ficha header shows the honest
  "sem foto" placeholder (class "ficha-foto--empty") and does not render an
  <img src="/alunos/{id}/foto"> tag.
- When the aluno has a photo (saved via save_foto + set_aluno_foto), the
  profile page renders <img class="ficha-foto" src="/alunos/{id}/foto">
  and does not show the empty placeholder.
- The same header is shared across sub-tabs: with a photo, GET
  /alunos/{id}/avaliacoes also shows the photo <img> tag.
- Nothing else on the profile broke: the aluno's name and fields (e.g.
  "Objetivo") are still shown.

Same isolation pattern as tests/test_foto_upload.py: KAIROS_DATA_DIR points
at a temp dir, the cached SQLAlchemy engine is disposed on teardown, and
TestClient is used as a context manager so the app's startup (migrations)
runs.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.fotos import save_foto
from kairos.alunos.service import create_aluno, set_aluno_foto
from kairos.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_profile_without_photo_shows_empty_placeholder(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    body = response.text
    assert "ficha-foto--empty" in body
    assert "sem foto" in body
    assert f'src="/alunos/{aluno["id"]}/foto"' not in body


def test_profile_with_photo_shows_img_tag(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")
        filename = save_foto(PNG, "image/png", "foto.png")
        set_aluno_foto(aluno["id"], filename)

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    body = response.text
    assert "<img" in body
    assert f'src="/alunos/{aluno["id"]}/foto"' in body
    assert 'class="ficha-foto"' in body
    assert "ficha-foto--empty" not in body


def test_avaliacoes_subtab_also_shows_photo(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")
        filename = save_foto(PNG, "image/png", "foto.png")
        set_aluno_foto(aluno["id"], filename)

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    assert f'src="/alunos/{aluno["id"]}/foto"' in response.text


def test_profile_still_shows_name_and_fields(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva", objective="Ganhar massa muscular")

        response = client.get(f"/alunos/{aluno['id']}")

    assert response.status_code == 200
    body = response.text
    assert "Marcos Silva" in body
    assert "Objetivo" in body
    assert "Ganhar massa muscular" in body
