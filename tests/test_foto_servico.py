"""Tests for the photo storage service (kairos/alunos/fotos.py).

Covers the functional specification (issue 02-foto-servico-armazenamento):
- save_foto() detects the image type from magic bytes (never the client's
  content-type or filename), writes the file under fotos_dir() with a
  server-generated uuid4().hex + extension name, and returns that name;
- the client-supplied original_filename is never used to build the name or
  the path on disk (defense against path traversal / extension spoofing);
- save_foto() rejects non-image bytes, empty bytes, and bytes larger than
  MAX_FOTO_BYTES, all via ValidationError;
- delete_foto_file() removes a saved file, is a no-op for a missing file or
  None, and refuses unsafe names (containing "..", "/" or "\\") without
  raising and without deleting anything outside fotos_dir();
- set_aluno_foto() updates (or clears) the "foto" column for an existing
  Aluno and returns the updated dict, or None when the id does not exist.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from pathlib import Path

import pytest

import kairos.db
from kairos import config
from kairos.alunos.fotos import MAX_FOTO_BYTES, delete_foto_file, save_foto
from kairos.alunos.service import ValidationError, create_aluno, get_aluno, set_aluno_foto
from kairos.migrations_runner import run_migrations

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 20


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# --- save_foto: valid images -------------------------------------------------


def test_save_foto_with_valid_png_returns_png_filename_and_writes_file(
    data_dir: Path,
) -> None:
    name = save_foto(PNG_BYTES, "image/png", "photo.png")

    assert name.endswith(".png")
    assert (config.fotos_dir() / name).exists()
    assert (config.fotos_dir() / name).read_bytes() == PNG_BYTES


def test_save_foto_with_valid_jpeg_returns_jpg_filename_and_writes_file(
    data_dir: Path,
) -> None:
    name = save_foto(JPEG_BYTES, "image/jpeg", "photo.jpg")

    assert name.endswith(".jpg")
    assert (config.fotos_dir() / name).exists()
    assert (config.fotos_dir() / name).read_bytes() == JPEG_BYTES


def test_save_foto_with_valid_webp_returns_webp_filename_and_writes_file(
    data_dir: Path,
) -> None:
    name = save_foto(WEBP_BYTES, "image/webp", "photo.webp")

    assert name.endswith(".webp")
    assert (config.fotos_dir() / name).exists()
    assert (config.fotos_dir() / name).read_bytes() == WEBP_BYTES


# --- save_foto: never trusts client-supplied name ---------------------------


def test_save_foto_ignores_client_supplied_original_filename(data_dir: Path) -> None:
    name = save_foto(PNG_BYTES, "image/png", "../../evil.php")

    assert name != "../../evil.php"
    assert "evil" not in name
    assert name.endswith(".png")

    saved_files = list(config.fotos_dir().iterdir())
    assert len(saved_files) == 1
    assert saved_files[0].name == name
    assert "evil" not in saved_files[0].name


# --- save_foto: validation errors -------------------------------------------


def test_save_foto_with_non_image_bytes_raises_validation_error(
    data_dir: Path,
) -> None:
    with pytest.raises(ValidationError):
        save_foto(b"not an image at all", "image/png", "photo.png")


def test_save_foto_with_empty_bytes_raises_validation_error(data_dir: Path) -> None:
    with pytest.raises(ValidationError):
        save_foto(b"", "image/png", "photo.png")


def test_save_foto_above_max_size_raises_validation_error(data_dir: Path) -> None:
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_FOTO_BYTES + 1)

    with pytest.raises(ValidationError):
        save_foto(oversized, "image/png", "photo.png")


# --- delete_foto_file --------------------------------------------------------


def test_delete_foto_file_removes_a_saved_file(data_dir: Path) -> None:
    name = save_foto(PNG_BYTES, "image/png", "photo.png")
    assert (config.fotos_dir() / name).exists()

    delete_foto_file(name)

    assert not (config.fotos_dir() / name).exists()


def test_delete_foto_file_of_nonexistent_name_does_not_raise(data_dir: Path) -> None:
    delete_foto_file("does-not-exist.png")  # should not raise


def test_delete_foto_file_of_none_does_not_raise(data_dir: Path) -> None:
    delete_foto_file(None)  # should not raise


def test_delete_foto_file_refuses_path_traversal_name(data_dir: Path) -> None:
    # Create a file outside fotos_dir() that a ".." traversal could reach.
    data_dir.mkdir(parents=True, exist_ok=True)
    outside_file = data_dir / "x"
    outside_file.write_bytes(b"do not delete me")

    delete_foto_file("../x")  # should not raise

    assert outside_file.exists()
    assert outside_file.read_bytes() == b"do not delete me"


# --- set_aluno_foto ----------------------------------------------------------


def test_set_aluno_foto_updates_foto_field_and_is_readable_via_get_aluno(
    data_dir: Path,
) -> None:
    run_migrations()
    aluno = create_aluno(name="Maria Silva")

    result = set_aluno_foto(aluno["id"], "abc.png")

    assert result is not None
    assert result["foto"] == "abc.png"
    loaded = get_aluno(aluno["id"])
    assert loaded is not None
    assert loaded["foto"] == "abc.png"


def test_set_aluno_foto_with_none_clears_foto_field(data_dir: Path) -> None:
    run_migrations()
    aluno = create_aluno(name="Joao Souza")
    set_aluno_foto(aluno["id"], "abc.png")

    result = set_aluno_foto(aluno["id"], None)

    assert result is not None
    assert result["foto"] is None
    loaded = get_aluno(aluno["id"])
    assert loaded is not None
    assert loaded["foto"] is None


def test_set_aluno_foto_with_nonexistent_id_returns_none(data_dir: Path) -> None:
    run_migrations()

    result = set_aluno_foto(999999, "abc.png")

    assert result is None
