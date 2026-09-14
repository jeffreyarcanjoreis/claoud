"""Tests for the exercise demonstration video upload (issue
06-treino-video-exercicio).

Mirrors the student photo upload tests (tests/test_foto_servico.py and
tests/test_foto_rota.py), applied to a per-exercise video stored locally.
Covers the functional specification:

- kairos.treinos.videos._detect_video_ext() detects MP4/WEBM/MOV from magic
  bytes only, never trusting the client's content-type or filename;
- save_video() rejects empty bytes, non-video bytes, and bytes larger than
  MAX_VIDEO_BYTES, all via ValidationError, and otherwise writes the file
  under config.videos_dir() with a server-generated uuid4().hex + extension
  name (never the client-supplied filename);
- delete_video_file() removes a saved file, is a no-op for a missing file or
  None, and refuses unsafe names (path traversal);
- set_exercicio_video() stores a new video for an existing exercise, swaps
  an existing one (deleting the old file only after the new one is saved),
  leaves everything untouched on a ValidationError, and returns None for a
  nonexistent exercise;
- remove_exercicio_video() clears the field and deletes the file, returning
  True/False depending on whether the exercise exists;
- get_treino_detail() exposes each item's video_filename (joined from its
  Exercicio);
- GET /exercicios/{id}/video serves the file (200) or 404 (missing exercise,
  no video, or an orphaned filename whose file is gone from disk);
- POST /exercicios/{id}/video uploads a video (303, reflected everywhere) or
  reexibits the planilha with a 400 error on an invalid upload, without
  touching the previous video;
- POST /exercicios/{id}/video/remover clears the video (303) or 404s for a
  nonexistent exercise.

Every test points KAIROS_DATA_DIR at a temporary directory and disposes the
cached SQLAlchemy engine on teardown so state never leaks between tests and
the SQLite file is not kept open on Windows.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.config
import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.treinos.service import (
    ValidationError,
    add_item_to_treino,
    create_exercicio,
    create_treino,
    get_exercicio,
    get_treino_detail,
    remove_exercicio_video,
    set_exercicio_video,
)
from kairos.treinos.videos import (
    MAX_VIDEO_BYTES,
    _detect_video_ext,
    delete_video_file,
    save_video,
)

# --- fixture magic-byte payloads --------------------------------------------

MP4_BYTES = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 20
MOV_BYTES_FTYP = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 20
MOV_BYTES_MOOV = b"\x00\x00\x00\x14moov" + b"\x00" * 20
WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"\x00" * 20
WEBM_BYTES_2 = b"\x1a\x45\xdf\xa3" + b"\x01" * 20
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# --------------------------------------------------------------------------- #
# 1. _detect_video_ext / save_video / delete_video_file                       #
# --------------------------------------------------------------------------- #


def test_detect_video_ext_recognizes_mp4() -> None:
    assert _detect_video_ext(MP4_BYTES) == "mp4"


def test_detect_video_ext_recognizes_mov_via_ftyp_qt_brand() -> None:
    assert _detect_video_ext(MOV_BYTES_FTYP) == "mov"


def test_detect_video_ext_recognizes_mov_via_moov_atom() -> None:
    assert _detect_video_ext(MOV_BYTES_MOOV) == "mov"


def test_detect_video_ext_recognizes_webm() -> None:
    assert _detect_video_ext(WEBM_BYTES) == "webm"


def test_detect_video_ext_returns_none_for_non_video_bytes() -> None:
    assert _detect_video_ext(b"hello") is None


def test_detect_video_ext_returns_none_for_an_image() -> None:
    assert _detect_video_ext(PNG_BYTES) is None


def test_detect_video_ext_returns_none_for_empty_bytes() -> None:
    assert _detect_video_ext(b"") is None


def test_save_video_with_valid_mp4_returns_mp4_filename_and_writes_file(
    data_dir: Path,
) -> None:
    name = save_video(MP4_BYTES, "video/mp4", "demo.mp4")

    assert name.endswith(".mp4")
    assert (kairos.config.videos_dir() / name).exists()
    assert (kairos.config.videos_dir() / name).read_bytes() == MP4_BYTES


def test_save_video_with_valid_webm_returns_webm_filename_and_writes_file(
    data_dir: Path,
) -> None:
    name = save_video(WEBM_BYTES, "video/webm", "demo.webm")

    assert name.endswith(".webm")
    assert (kairos.config.videos_dir() / name).exists()
    assert (kairos.config.videos_dir() / name).read_bytes() == WEBM_BYTES


def test_save_video_with_valid_mov_returns_mov_filename_and_writes_file(
    data_dir: Path,
) -> None:
    name = save_video(MOV_BYTES_FTYP, "video/quicktime", "demo.mov")

    assert name.endswith(".mov")
    assert (kairos.config.videos_dir() / name).exists()
    assert (kairos.config.videos_dir() / name).read_bytes() == MOV_BYTES_FTYP


def test_save_video_ignores_client_supplied_original_filename(data_dir: Path) -> None:
    name = save_video(MP4_BYTES, "video/mp4", "../../evil.php")

    assert name != "../../evil.php"
    assert "evil" not in name
    assert name.endswith(".mp4")

    saved_files = list(kairos.config.videos_dir().iterdir())
    assert len(saved_files) == 1
    assert saved_files[0].name == name
    assert "evil" not in saved_files[0].name


def test_save_video_name_is_a_uuid_hex_not_the_client_filename(data_dir: Path) -> None:
    import uuid

    name = save_video(MP4_BYTES, "video/mp4", "meu-video-favorito.mp4")

    stem, ext = name.rsplit(".", 1)
    assert ext == "mp4"
    # Must parse as a uuid4 hex string (raises ValueError otherwise).
    uuid.UUID(hex=stem)


def test_save_video_with_non_video_bytes_raises_validation_error(
    data_dir: Path,
) -> None:
    with pytest.raises(ValidationError):
        save_video(b"not a video at all", "video/mp4", "demo.mp4")


def test_save_video_with_image_bytes_raises_validation_error(data_dir: Path) -> None:
    with pytest.raises(ValidationError):
        save_video(PNG_BYTES, "video/mp4", "demo.mp4")


def test_save_video_with_empty_bytes_raises_validation_error(data_dir: Path) -> None:
    with pytest.raises(ValidationError):
        save_video(b"", "video/mp4", "demo.mp4")


def test_save_video_above_max_size_raises_validation_error(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Avoid allocating 50 MB of bytes in the test: shrink the limit instead.
    monkeypatch.setattr("kairos.treinos.videos.MAX_VIDEO_BYTES", 100)
    oversized = MP4_BYTES + b"\x00" * 200
    assert len(oversized) > 100

    with pytest.raises(ValidationError):
        save_video(oversized, "video/mp4", "demo.mp4")


def test_max_video_bytes_constant_is_fifty_megabytes() -> None:
    assert MAX_VIDEO_BYTES == 50 * 1024 * 1024


def test_delete_video_file_removes_a_saved_file(data_dir: Path) -> None:
    name = save_video(MP4_BYTES, "video/mp4", "demo.mp4")
    assert (kairos.config.videos_dir() / name).exists()

    delete_video_file(name)

    assert not (kairos.config.videos_dir() / name).exists()


def test_delete_video_file_of_nonexistent_name_does_not_raise(data_dir: Path) -> None:
    delete_video_file("does-not-exist.mp4")  # should not raise


def test_delete_video_file_of_none_does_not_raise(data_dir: Path) -> None:
    delete_video_file(None)  # should not raise


def test_delete_video_file_refuses_path_traversal_name(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    outside_file = data_dir / "x"
    outside_file.write_bytes(b"do not delete me")

    delete_video_file("../x")  # should not raise

    assert outside_file.exists()
    assert outside_file.read_bytes() == b"do not delete me"


# --------------------------------------------------------------------------- #
# 2. set_exercicio_video                                                      #
# --------------------------------------------------------------------------- #


def test_set_exercicio_video_stores_new_video_and_updates_field(data_dir: Path) -> None:
    with TestClient(app):
        ex = create_exercicio(nome="Supino")

        result = set_exercicio_video(ex["id"], MP4_BYTES, "video/mp4", "demo.mp4")

        assert result is not None
        assert result["video_filename"] is not None
        assert result["video_filename"].endswith(".mp4")
        assert (kairos.config.videos_dir() / result["video_filename"]).exists()

        loaded = get_exercicio(ex["id"])
        assert loaded["video_filename"] == result["video_filename"]


def test_set_exercicio_video_replaces_old_video_and_deletes_old_file(
    data_dir: Path,
) -> None:
    with TestClient(app):
        ex = create_exercicio(nome="Supino")
        first = set_exercicio_video(ex["id"], MP4_BYTES, "video/mp4", "demo.mp4")
        old_name = first["video_filename"]
        assert (kairos.config.videos_dir() / old_name).exists()

        second = set_exercicio_video(ex["id"], WEBM_BYTES, "video/webm", "demo.webm")
        new_name = second["video_filename"]

        assert new_name != old_name
        assert not (kairos.config.videos_dir() / old_name).exists()
        assert (kairos.config.videos_dir() / new_name).exists()
        assert (kairos.config.videos_dir() / new_name).read_bytes() == WEBM_BYTES


def test_set_exercicio_video_with_invalid_bytes_raises_and_keeps_old_video(
    data_dir: Path,
) -> None:
    with TestClient(app):
        ex = create_exercicio(nome="Supino")
        first = set_exercicio_video(ex["id"], MP4_BYTES, "video/mp4", "demo.mp4")
        old_name = first["video_filename"]

        with pytest.raises(ValidationError):
            set_exercicio_video(ex["id"], b"not a video", "video/mp4", "demo.mp4")

        loaded = get_exercicio(ex["id"])
        assert loaded["video_filename"] == old_name
        assert (kairos.config.videos_dir() / old_name).exists()
        assert (kairos.config.videos_dir() / old_name).read_bytes() == MP4_BYTES
        # Nothing else was left over on disk.
        assert [p.name for p in kairos.config.videos_dir().iterdir()] == [old_name]


def test_set_exercicio_video_with_empty_bytes_raises_and_keeps_old_video(
    data_dir: Path,
) -> None:
    with TestClient(app):
        ex = create_exercicio(nome="Supino")
        first = set_exercicio_video(ex["id"], MP4_BYTES, "video/mp4", "demo.mp4")
        old_name = first["video_filename"]

        with pytest.raises(ValidationError):
            set_exercicio_video(ex["id"], b"", "video/mp4", "demo.mp4")

        loaded = get_exercicio(ex["id"])
        assert loaded["video_filename"] == old_name


def test_set_exercicio_video_for_nonexistent_exercicio_returns_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        result = set_exercicio_video(999999, MP4_BYTES, "video/mp4", "demo.mp4")

    assert result is None
    videos_dir = kairos.config.videos_dir()
    assert not videos_dir.exists() or list(videos_dir.iterdir()) == []


# --------------------------------------------------------------------------- #
# 3. remove_exercicio_video                                                   #
# --------------------------------------------------------------------------- #


def test_remove_exercicio_video_clears_field_and_deletes_file(data_dir: Path) -> None:
    with TestClient(app):
        ex = create_exercicio(nome="Supino")
        result = set_exercicio_video(ex["id"], MP4_BYTES, "video/mp4", "demo.mp4")
        name = result["video_filename"]
        assert (kairos.config.videos_dir() / name).exists()

        removed = remove_exercicio_video(ex["id"])

        assert removed is True
        loaded = get_exercicio(ex["id"])
        assert loaded["video_filename"] is None
        assert not (kairos.config.videos_dir() / name).exists()


def test_remove_exercicio_video_for_nonexistent_exercicio_returns_false(
    data_dir: Path,
) -> None:
    with TestClient(app):
        removed = remove_exercicio_video(999999)

    assert removed is False


# --------------------------------------------------------------------------- #
# 4. get_treino_detail exposes video_filename                                 #
# --------------------------------------------------------------------------- #


def test_get_treino_detail_item_exposes_video_filename_when_exercicio_has_video(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        set_exercicio_video(ex["id"], MP4_BYTES, "video/mp4", "demo.mp4")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        detalhe = get_treino_detail(treino["id"])

    item = detalhe["itens"][0]
    assert item["video_filename"] is not None
    assert item["video_filename"] == get_exercicio(ex["id"])["video_filename"]


def test_get_treino_detail_item_exposes_none_when_exercicio_has_no_video(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Agachamento")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        detalhe = get_treino_detail(treino["id"])

    item = detalhe["itens"][0]
    assert item["video_filename"] is None


# --------------------------------------------------------------------------- #
# 5. Routes                                                                   #
# --------------------------------------------------------------------------- #


def test_get_video_route_returns_200_with_bytes_and_content_type(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        ex = create_exercicio(nome="Supino")
        set_exercicio_video(ex["id"], MP4_BYTES, "video/mp4", "demo.mp4")

        response = client.get(f"/exercicios/{ex['id']}/video")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == MP4_BYTES


def test_get_video_route_returns_200_for_webm_with_webm_content_type(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        ex = create_exercicio(nome="Supino")
        set_exercicio_video(ex["id"], WEBM_BYTES, "video/webm", "demo.webm")

        response = client.get(f"/exercicios/{ex['id']}/video")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/webm")


def test_get_video_route_404_for_nonexistent_exercicio(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/exercicios/999999/video")

    assert response.status_code == 404


def test_get_video_route_404_when_exercicio_has_no_video(data_dir: Path) -> None:
    with TestClient(app) as client:
        ex = create_exercicio(nome="Supino")

        response = client.get(f"/exercicios/{ex['id']}/video")

    assert response.status_code == 404


def test_get_video_route_404_when_file_is_orphaned(data_dir: Path) -> None:
    with TestClient(app) as client:
        ex = create_exercicio(nome="Supino")
        result = set_exercicio_video(ex["id"], MP4_BYTES, "video/mp4", "demo.mp4")
        (kairos.config.videos_dir() / result["video_filename"]).unlink()

        response = client.get(f"/exercicios/{ex['id']}/video")

    assert response.status_code == 404


def test_post_upload_valid_video_redirects_and_reflects_in_treino_detail(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        response = client.post(
            f"/exercicios/{ex['id']}/video",
            files={"video": ("demo.mp4", MP4_BYTES, "video/mp4")},
            data={
                "aluno_id": str(aluno["id"]),
                "treino_id": str(treino["id"]),
                "next": f"/alunos/{aluno['id']}/treino/{treino['id']}",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert (
            response.headers["location"]
            == f"/alunos/{aluno['id']}/treino/{treino['id']}"
        )

        detalhe = get_treino_detail(treino["id"])
        assert detalhe["itens"][0]["video_filename"] is not None

        video_response = client.get(f"/exercicios/{ex['id']}/video")

    assert video_response.status_code == 200
    assert video_response.content == MP4_BYTES


def test_post_upload_invalid_video_returns_400_and_reexibits_planilha(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        response = client.post(
            f"/exercicios/{ex['id']}/video",
            files={"video": ("demo.txt", b"not a video", "text/plain")},
            data={
                "aluno_id": str(aluno["id"]),
                "treino_id": str(treino["id"]),
                "next": f"/alunos/{aluno['id']}/treino/{treino['id']}",
            },
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert "message-error" in response.text
        assert "vídeo" in response.text

        detalhe = get_treino_detail(treino["id"])

    assert detalhe["itens"][0]["video_filename"] is None


def test_post_upload_invalid_video_keeps_existing_video_unchanged(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))

        first = client.post(
            f"/exercicios/{ex['id']}/video",
            files={"video": ("demo.mp4", MP4_BYTES, "video/mp4")},
            data={
                "aluno_id": str(aluno["id"]),
                "treino_id": str(treino["id"]),
                "next": f"/alunos/{aluno['id']}/treino/{treino['id']}",
            },
            follow_redirects=False,
        )
        assert first.status_code == 303
        old_name = get_exercicio(ex["id"])["video_filename"]

        second = client.post(
            f"/exercicios/{ex['id']}/video",
            files={"video": ("demo.txt", b"not a video", "text/plain")},
            data={
                "aluno_id": str(aluno["id"]),
                "treino_id": str(treino["id"]),
                "next": f"/alunos/{aluno['id']}/treino/{treino['id']}",
            },
            follow_redirects=False,
        )

        assert second.status_code == 400
        loaded = get_exercicio(ex["id"])

    assert loaded["video_filename"] == old_name
    assert (kairos.config.videos_dir() / old_name).exists()


def test_post_upload_video_for_nonexistent_exercicio_returns_404(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/exercicios/999999/video",
            files={"video": ("demo.mp4", MP4_BYTES, "video/mp4")},
            data={},
            follow_redirects=False,
        )

    assert response.status_code == 404


def test_post_upload_video_without_planilha_context_redirects_to_next(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        ex = create_exercicio(nome="Supino")

        response = client.post(
            f"/exercicios/{ex['id']}/video",
            files={"video": ("demo.mp4", MP4_BYTES, "video/mp4")},
            data={"next": "/treinos"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/treinos"
    assert get_exercicio(ex["id"])["video_filename"] is not None


def test_post_upload_video_without_planilha_context_or_next_defaults_to_biblioteca(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        ex = create_exercicio(nome="Supino")

        response = client.post(
            f"/exercicios/{ex['id']}/video",
            files={"video": ("demo.mp4", MP4_BYTES, "video/mp4")},
            data={},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/treinos"


def test_post_remove_video_route_redirects_and_clears_video(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        set_exercicio_video(ex["id"], MP4_BYTES, "video/mp4", "demo.mp4")

        response = client.post(
            f"/exercicios/{ex['id']}/video/remover",
            data={
                "aluno_id": str(aluno["id"]),
                "treino_id": str(treino["id"]),
                "next": f"/alunos/{aluno['id']}/treino/{treino['id']}",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert (
            response.headers["location"]
            == f"/alunos/{aluno['id']}/treino/{treino['id']}"
        )

        detalhe = get_treino_detail(treino["id"])
        video_response = client.get(f"/exercicios/{ex['id']}/video")

    assert detalhe["itens"][0]["video_filename"] is None
    assert video_response.status_code == 404


def test_post_remove_video_for_nonexistent_exercicio_returns_404(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/exercicios/999999/video/remover", data={}, follow_redirects=False
        )

    assert response.status_code == 404
