"""Tests for photo upload/removal on the edit form (issue 04-foto-upload-editar).

Covers the functional specification:
- GET /alunos/{id}/editar shows a file input for the photo and the form is
  multipart/form-data;
- POST /alunos/{id} with a valid image saves the photo (303, foto set,
  GET /foto returns 200);
- POST with a non-image file returns 400 and changes nothing (foto stays
  None, text fields are not applied);
- Replacing a photo deletes the old file from disk and keeps only the new
  one;
- "remover_foto" clears the foto field and deletes the file (GET /foto
  becomes 404);
- Saving without sending a file (and without "remover_foto") keeps the
  current photo unchanged;
- Atomicity: invalid text fields alongside a valid new image roll back the
  new file and keep the old photo;
- The new-student form does not show the photo field.

Same isolation pattern as tests/test_foto_rota.py: KAIROS_DATA_DIR points at
a temp dir, the cached SQLAlchemy engine is disposed on teardown, and
TestClient is used as a context manager so the app's startup (migrations)
runs.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.config
import kairos.db
from kairos.alunos.service import create_aluno, get_aluno
from kairos.main import app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PNG_2 = b"\x89PNG\r\n\x1a\n" + b"\x01" * 32


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_edit_form_shows_photo_field_as_multipart(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")

        response = client.get(f"/alunos/{aluno['id']}/editar")

    assert response.status_code == 200
    body = response.text
    assert 'type="file"' in body
    assert 'name="foto"' in body
    assert 'enctype="multipart/form-data"' in body


def test_post_edit_with_valid_photo_saves_it_and_redirects(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")

        response = client.post(
            f"/alunos/{aluno['id']}",
            data={"name": "Marcos", "status": "active"},
            files={"foto": ("x.png", PNG, "image/png")},
            follow_redirects=False,
        )

        assert response.status_code == 303

        updated = get_aluno(aluno["id"])
        assert updated["foto"] is not None

        foto_response = client.get(f"/alunos/{aluno['id']}/foto")

    assert foto_response.status_code == 200


def test_post_edit_with_non_image_file_returns_400_and_changes_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")

        response = client.post(
            f"/alunos/{aluno['id']}",
            data={"name": "Outro Nome", "status": "active"},
            files={"foto": ("x.txt", b"not an image", "text/plain")},
            follow_redirects=False,
        )

        assert response.status_code == 400

        unchanged = get_aluno(aluno["id"])

    assert unchanged["foto"] is None
    assert unchanged["name"] == "Marcos Silva"


def test_post_edit_replacing_photo_deletes_old_file_from_disk(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")

        first = client.post(
            f"/alunos/{aluno['id']}",
            data={"name": "Marcos", "status": "active"},
            files={"foto": ("a.png", PNG, "image/png")},
            follow_redirects=False,
        )
        assert first.status_code == 303
        nome_a = get_aluno(aluno["id"])["foto"]
        assert nome_a is not None

        second = client.post(
            f"/alunos/{aluno['id']}",
            data={"name": "Marcos", "status": "active"},
            files={"foto": ("b.png", PNG_2, "image/png")},
            follow_redirects=False,
        )
        assert second.status_code == 303
        nome_b = get_aluno(aluno["id"])["foto"]

    assert nome_b is not None
    assert nome_b != nome_a
    assert not (kairos.config.fotos_dir() / nome_a).exists()
    assert (kairos.config.fotos_dir() / nome_b).exists()


def test_post_edit_with_remover_foto_clears_photo_and_deletes_file(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")

        upload = client.post(
            f"/alunos/{aluno['id']}",
            data={"name": "Marcos", "status": "active"},
            files={"foto": ("a.png", PNG, "image/png")},
            follow_redirects=False,
        )
        assert upload.status_code == 303
        nome_a = get_aluno(aluno["id"])["foto"]
        assert nome_a is not None

        response = client.post(
            f"/alunos/{aluno['id']}",
            data={"name": "Marcos", "status": "active", "remover_foto": "1"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        updated = get_aluno(aluno["id"])
        foto_response = client.get(f"/alunos/{aluno['id']}/foto")

    assert updated["foto"] is None
    assert foto_response.status_code == 404
    assert not (kairos.config.fotos_dir() / nome_a).exists()


def test_post_edit_without_file_keeps_current_photo_unchanged(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")

        upload = client.post(
            f"/alunos/{aluno['id']}",
            data={"name": "Marcos", "status": "active"},
            files={"foto": ("a.png", PNG, "image/png")},
            follow_redirects=False,
        )
        assert upload.status_code == 303
        nome_a = get_aluno(aluno["id"])["foto"]
        assert nome_a is not None

        response = client.post(
            f"/alunos/{aluno['id']}",
            data={"name": "Marcos", "status": "active"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        updated = get_aluno(aluno["id"])

    assert updated["foto"] == nome_a


def test_post_edit_with_invalid_text_and_valid_photo_rolls_back_new_photo(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Silva")

        upload = client.post(
            f"/alunos/{aluno['id']}",
            data={"name": "Marcos", "status": "active"},
            files={"foto": ("a.png", PNG, "image/png")},
            follow_redirects=False,
        )
        assert upload.status_code == 303
        nome_a = get_aluno(aluno["id"])["foto"]
        assert nome_a is not None

        response = client.post(
            f"/alunos/{aluno['id']}",
            data={
                "name": "Marcos",
                "status": "active",
                "plan_start": "2024-02-15",
                "plan_end": "2024-01-01",
            },
            files={"foto": ("b.png", PNG_2, "image/png")},
            follow_redirects=False,
        )

        assert response.status_code == 400

        unchanged = get_aluno(aluno["id"])

    assert unchanged["foto"] == nome_a
    assert (kairos.config.fotos_dir() / nome_a).exists()


def test_new_aluno_form_does_not_show_photo_field(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/novo")

    assert response.status_code == 200
    assert 'name="foto"' not in response.text
