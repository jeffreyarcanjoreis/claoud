"""Tests for issue 11: the student's execution attachment (photo/video upload
plus a written observation).

Covers kairos.execucao.anexos (magic-byte detection, size/empty validation,
uuid filename, delete), the service (adicionar_anexo, list_anexos, get_anexo,
remove_anexo, anexos_do_treino), the aluno routes (upload, serve, remove,
ownership 404s, orphan file 404) and the coach route that serves the file.

Every test points KAIROS_DATA_DIR at a temp dir (files go to tmp too).
"""

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.config
import kairos.db
from kairos.alunos.service import create_aluno
from kairos.execucao.anexos import (
    MAX_ANEXO_BYTES,
    _detect_anexo,
    delete_anexo_file,
    save_anexo,
)
from kairos.execucao.service import (
    adicionar_anexo,
    anexos_do_treino,
    get_anexo,
    list_anexos,
    remove_anexo,
)
from kairos.main import app
from kairos.treinos.service import (
    ValidationError,
    add_item_to_treino,
    create_exercicio,
    create_treino,
)

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20
MP4_BYTES = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 20
MOV_BYTES = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 20
WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"\x00" * 20


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def _login_as_aluno(monkeypatch: pytest.MonkeyPatch, aluno_id) -> None:
    fake_current_user = lambda request: {
        "user_id": "uid-aluno",
        "email": "aluno@x.com",
        "papel": "aluno",
        "aluno_id": aluno_id,
    }
    monkeypatch.setattr("kairos.auth.middleware.current_user", fake_current_user)
    monkeypatch.setattr("kairos.area_aluno.routes.current_user", fake_current_user)


def _setup(nome: str = "Ana"):
    aluno = create_aluno(name=nome)
    ex = create_exercicio(nome=f"Supino {nome}")
    treino = create_treino(aluno["id"], nome="Treino A")
    item = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
    return aluno, treino, item


def _upload_url(treino, item) -> str:
    return f"/aluno/treinos/{treino['id']}/itens/{item['id']}/anexo"


def _files_on_disk() -> list:
    d = kairos.config.anexos_dir()
    return [] if not d.exists() else list(d.iterdir())


# --------------------------------------------------------------------------- #
# 1. anexos.py                                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "data,expected",
    [
        (JPEG_BYTES, ("jpg", "imagem")),
        (PNG_BYTES, ("png", "imagem")),
        (WEBP_BYTES, ("webp", "imagem")),
        (MP4_BYTES, ("mp4", "video")),
        (WEBM_BYTES, ("webm", "video")),
        (MOV_BYTES, ("mov", "video")),
        (b"\x00\x00\x00\x14moov" + b"\x00" * 20, ("mov", "video")),
    ],
)
def test_detect_anexo_recognizes_images_and_videos(data, expected) -> None:
    assert _detect_anexo(data) == expected


@pytest.mark.parametrize("data", [b"hello world, not media", b"", b"%PDF-1.4 xxxxxxxx"])
def test_detect_anexo_returns_none_for_non_media(data) -> None:
    assert _detect_anexo(data) is None


@pytest.mark.parametrize(
    "data,ext,tipo",
    [
        (JPEG_BYTES, "jpg", "imagem"),
        (PNG_BYTES, "png", "imagem"),
        (WEBP_BYTES, "webp", "imagem"),
        (MP4_BYTES, "mp4", "video"),
        (WEBM_BYTES, "webm", "video"),
        (MOV_BYTES, "mov", "video"),
    ],
)
def test_save_anexo_accepts_media_and_writes_file(
    data_dir: Path, data, ext, tipo
) -> None:
    name, got_tipo = save_anexo(data, "application/octet-stream", "x." + ext)

    assert got_tipo == tipo
    assert name.endswith("." + ext)
    path = kairos.config.anexos_dir() / name
    assert path.exists()
    assert path.read_bytes() == data
    assert path.parent == data_dir / "anexos"


def test_save_anexo_ignores_client_content_type_and_filename(data_dir: Path) -> None:
    name, tipo = save_anexo(PNG_BYTES, "video/mp4", "../../evil.php")

    assert tipo == "imagem"
    assert name.endswith(".png")
    assert "evil" not in name
    assert [p.name for p in kairos.config.anexos_dir().iterdir()] == [name]


def test_save_anexo_name_is_uuid_hex_plus_extension(data_dir: Path) -> None:
    name, _ = save_anexo(MP4_BYTES, "video/mp4", "meu-video.mp4")

    stem, ext = name.rsplit(".", 1)
    assert ext == "mp4"
    assert uuid.UUID(hex=stem).hex == stem


def test_save_anexo_with_non_media_bytes_raises_and_writes_nothing(
    data_dir: Path,
) -> None:
    with pytest.raises(ValidationError):
        save_anexo(b"just some text", "image/png", "a.png")
    assert _files_on_disk() == []


def test_save_anexo_with_empty_bytes_raises(data_dir: Path) -> None:
    with pytest.raises(ValidationError):
        save_anexo(b"", "image/png", "a.png")
    assert _files_on_disk() == []


def test_save_anexo_above_max_size_raises(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("kairos.execucao.anexos.MAX_ANEXO_BYTES", 100)
    with pytest.raises(ValidationError):
        save_anexo(MP4_BYTES + b"\x00" * 200, "video/mp4", "a.mp4")
    assert _files_on_disk() == []


def test_max_anexo_bytes_is_fifty_megabytes() -> None:
    assert MAX_ANEXO_BYTES == 50 * 1024 * 1024


def test_anexos_dir_is_under_data_dir(data_dir: Path) -> None:
    assert kairos.config.anexos_dir() == data_dir / "anexos"


def test_delete_anexo_file_removes_saved_file(data_dir: Path) -> None:
    name, _ = save_anexo(PNG_BYTES, "image/png", "a.png")

    delete_anexo_file(name)

    assert not (kairos.config.anexos_dir() / name).exists()


def test_delete_anexo_file_is_noop_for_missing_or_falsy(data_dir: Path) -> None:
    delete_anexo_file("does-not-exist.png")
    delete_anexo_file(None)
    delete_anexo_file("")


def test_delete_anexo_file_refuses_path_traversal(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    outside = data_dir / "x"
    outside.write_bytes(b"keep me")

    delete_anexo_file("../x")

    assert outside.read_bytes() == b"keep me"


# --------------------------------------------------------------------------- #
# 2. Service                                                                  #
# --------------------------------------------------------------------------- #


def test_adicionar_anexo_creates_row_and_file(data_dir: Path) -> None:
    with TestClient(app):
        _, _, item = _setup()

        result = adicionar_anexo(
            item["id"], PNG_BYTES, "image/png", "foto.png", observacao="Olhem o joelho"
        )

        loaded = get_anexo(result["id"])
        listed = list_anexos(item["id"])

    assert loaded["treino_item_id"] == item["id"]
    assert loaded["tipo"] == "imagem"
    assert loaded["observacao"] == "Olhem o joelho"
    assert loaded["filename"].endswith(".png")
    assert loaded["filename"] != "foto.png"
    assert (kairos.config.anexos_dir() / loaded["filename"]).read_bytes() == PNG_BYTES
    assert [a["id"] for a in listed] == [result["id"]]


def test_adicionar_anexo_video_has_tipo_video(data_dir: Path) -> None:
    with TestClient(app):
        _, _, item = _setup()
        result = adicionar_anexo(item["id"], MP4_BYTES, "video/mp4", "v.mp4")

    assert result["tipo"] == "video"


@pytest.mark.parametrize("obs", [None, "", "   "])
def test_adicionar_anexo_empty_observacao_is_none(data_dir: Path, obs) -> None:
    with TestClient(app):
        _, _, item = _setup()
        result = adicionar_anexo(item["id"], PNG_BYTES, "image/png", "a.png", obs)
        loaded = get_anexo(result["id"])

    assert result["observacao"] is None
    assert loaded["observacao"] is None


def test_adicionar_anexo_nonexistent_item_raises_and_leaves_no_file(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            adicionar_anexo(999999, PNG_BYTES, "image/png", "a.png")

    assert _files_on_disk() == []


def test_adicionar_anexo_invalid_file_raises_and_persists_nothing(
    data_dir: Path,
) -> None:
    with TestClient(app):
        _, _, item = _setup()
        with pytest.raises(ValidationError):
            adicionar_anexo(item["id"], b"not media", "image/png", "a.png")
        rows = list_anexos(item["id"])

    assert rows == []
    assert _files_on_disk() == []


def test_list_anexos_returns_all_for_item_most_recent_first(data_dir: Path) -> None:
    with TestClient(app):
        _, _, item = _setup()
        first = adicionar_anexo(item["id"], PNG_BYTES, "image/png", "a.png")
        second = adicionar_anexo(item["id"], MP4_BYTES, "video/mp4", "b.mp4")
        third = adicionar_anexo(item["id"], JPEG_BYTES, "image/jpeg", "c.jpg")

        rows = list_anexos(item["id"])

    assert [r["id"] for r in rows] == [third["id"], second["id"], first["id"]]


def test_list_anexos_of_item_without_anexos_is_empty(data_dir: Path) -> None:
    with TestClient(app):
        _, _, item = _setup()
        assert list_anexos(item["id"]) == []


def test_get_anexo_unknown_id_returns_none(data_dir: Path) -> None:
    with TestClient(app):
        assert get_anexo(999999) is None


def test_remove_anexo_deletes_row_and_file(data_dir: Path) -> None:
    with TestClient(app):
        _, _, item = _setup()
        result = adicionar_anexo(item["id"], PNG_BYTES, "image/png", "a.png")
        path = kairos.config.anexos_dir() / result["filename"]
        assert path.exists()

        assert remove_anexo(result["id"]) is True

        assert get_anexo(result["id"]) is None
        assert list_anexos(item["id"]) == []
    assert not path.exists()


def test_remove_anexo_unknown_id_returns_false(data_dir: Path) -> None:
    with TestClient(app):
        assert remove_anexo(999999) is False


def test_anexos_do_treino_maps_by_item(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino = create_treino(aluno["id"], nome="Treino A")
        item1 = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        item2 = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        item3 = add_item_to_treino(treino["id"], exercicio_id=str(ex["id"]))
        a1 = adicionar_anexo(item1["id"], PNG_BYTES, "image/png", "a.png")
        a2 = adicionar_anexo(item1["id"], MP4_BYTES, "video/mp4", "b.mp4")
        a3 = adicionar_anexo(item2["id"], JPEG_BYTES, "image/jpeg", "c.jpg")

        # Another treino's anexo must not leak in.
        _, _, other_item = _setup("Bruno")
        adicionar_anexo(other_item["id"], PNG_BYTES, "image/png", "d.png")

        mapa = anexos_do_treino(treino["id"])

    assert set(mapa.keys()) == {item1["id"], item2["id"]}
    assert item3["id"] not in mapa
    assert [a["id"] for a in mapa[item1["id"]]] == [a2["id"], a1["id"]]
    assert [a["id"] for a in mapa[item2["id"]]] == [a3["id"]]


def test_anexos_do_treino_without_anexos_is_empty(data_dir: Path) -> None:
    with TestClient(app):
        _, treino, _ = _setup()
        assert anexos_do_treino(treino["id"]) == {}


# --------------------------------------------------------------------------- #
# 3. Aluno routes                                                             #
# --------------------------------------------------------------------------- #


def test_post_upload_redirects_and_get_page_reflects_media_and_observacao(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, item = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            _upload_url(treino, item),
            files={"anexo": ("x.png", PNG_BYTES, "image/png")},
            data={"observacao": "Vejam a postura"},
            follow_redirects=False,
        )
        rows = list_anexos(item["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert response.status_code == 303
    assert response.headers["location"] == f"/aluno/treinos/{treino['id']}"
    assert len(rows) == 1
    assert rows[0]["tipo"] == "imagem"
    assert rows[0]["observacao"] == "Vejam a postura"
    assert page.status_code == 200
    assert f"/aluno/anexos/{rows[0]['id']}" in page.text
    assert "<img" in page.text and "anexo-midia" in page.text
    assert "Vejam a postura" in page.text


def test_post_upload_video_renders_video_tag(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, item = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        client.post(
            _upload_url(treino, item),
            files={"anexo": ("x.mp4", MP4_BYTES, "video/mp4")},
            data={"observacao": ""},
            follow_redirects=False,
        )
        rows = list_anexos(item["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert rows[0]["tipo"] == "video"
    assert rows[0]["observacao"] is None
    assert f'<video src="/aluno/anexos/{rows[0]["id"]}"' in page.text


def test_page_without_anexos_has_no_anexo_list(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, _ = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.status_code == 200
    assert "anexos-lista" not in page.text


def test_post_upload_multiple_anexos_to_same_item_keeps_all(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, item = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        for name, data, ctype in [
            ("a.png", PNG_BYTES, "image/png"),
            ("b.mp4", MP4_BYTES, "video/mp4"),
        ]:
            client.post(
                _upload_url(treino, item),
                files={"anexo": (name, data, ctype)},
                follow_redirects=False,
            )
        rows = list_anexos(item["id"])

    assert len(rows) == 2


def test_post_upload_invalid_text_file_is_noop_with_redirect(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, item = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            _upload_url(treino, item),
            files={"anexo": ("x.txt", b"plain text", "text/plain")},
            data={"observacao": "nada"},
            follow_redirects=False,
        )
        rows = list_anexos(item["id"])

    assert response.status_code == 303
    assert rows == []
    assert _files_on_disk() == []


def test_post_upload_empty_file_is_noop(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, item = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            _upload_url(treino, item),
            files={"anexo": ("x.png", b"", "image/png")},
            follow_redirects=False,
        )
        rows = list_anexos(item["id"])

    assert response.status_code == 303
    assert rows == []


def test_post_upload_on_another_alunos_treino_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a, _, _ = _setup("Aluno A")
        _, treino_b, item_b = _setup("Aluno B")
        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.post(
            _upload_url(treino_b, item_b),
            files={"anexo": ("x.png", PNG_BYTES, "image/png")},
            follow_redirects=False,
        )
        rows = list_anexos(item_b["id"])

    assert response.status_code == 404
    assert rows == []
    assert _files_on_disk() == []


def test_post_upload_for_item_outside_treino_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        ex = create_exercicio(nome="Supino")
        treino_a = create_treino(aluno["id"], nome="A")
        treino_b = create_treino(aluno["id"], nome="B")
        item_b = add_item_to_treino(treino_b["id"], exercicio_id=str(ex["id"]))
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post(
            _upload_url(treino_a, item_b),
            files={"anexo": ("x.png", PNG_BYTES, "image/png")},
            follow_redirects=False,
        )

    assert response.status_code == 404
    assert list_anexos(item_b["id"]) == []


@pytest.mark.parametrize(
    "data,ctype,expected",
    [
        (PNG_BYTES, "image/png", "image/png"),
        (JPEG_BYTES, "image/jpeg", "image/jpeg"),
        (WEBP_BYTES, "image/webp", "image/webp"),
        (MP4_BYTES, "video/mp4", "video/mp4"),
        (WEBM_BYTES, "video/webm", "video/webm"),
    ],
)
def test_get_anexo_serves_file_with_correct_content_type(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch, data, ctype, expected
) -> None:
    with TestClient(app) as client:
        aluno, _, item = _setup()
        anexo = adicionar_anexo(item["id"], data, ctype, "x")
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/anexos/{anexo['id']}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(expected)
    assert response.content == data


def test_get_anexo_of_mov_has_quicktime_or_video_content_type(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, _, item = _setup()
        anexo = adicionar_anexo(item["id"], MOV_BYTES, "video/quicktime", "x.mov")
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/anexos/{anexo['id']}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/")


def test_get_anexo_of_another_aluno_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a, _, _ = _setup("Aluno A")
        _, _, item_b = _setup("Aluno B")
        anexo_b = adicionar_anexo(item_b["id"], PNG_BYTES, "image/png", "x.png")
        _login_as_aluno(monkeypatch, aluno_a["id"])
        response = client.get(f"/aluno/anexos/{anexo_b['id']}")

    assert response.status_code == 404


def test_get_anexo_unknown_id_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, _, _ = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get("/aluno/anexos/999999")

    assert response.status_code == 404


def test_get_anexo_orphan_file_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, _, item = _setup()
        anexo = adicionar_anexo(item["id"], PNG_BYTES, "image/png", "x.png")
        (kairos.config.anexos_dir() / anexo["filename"]).unlink()
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.get(f"/aluno/anexos/{anexo['id']}")

    assert response.status_code == 404


def test_post_remover_redirects_and_removes_row_and_file(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, treino, item = _setup()
        anexo = adicionar_anexo(item["id"], PNG_BYTES, "image/png", "x.png")
        _login_as_aluno(monkeypatch, aluno["id"])

        response = client.post(
            f"/aluno/anexos/{anexo['id']}/remover", follow_redirects=False
        )
        after = client.get(f"/aluno/anexos/{anexo['id']}")

    assert response.status_code == 303
    assert response.headers["location"] == f"/aluno/treinos/{treino['id']}"
    assert get_anexo(anexo["id"]) is None
    assert after.status_code == 404
    assert _files_on_disk() == []


def test_post_remover_anexo_of_another_aluno_returns_404_and_keeps_it(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno_a, _, _ = _setup("Aluno A")
        _, _, item_b = _setup("Aluno B")
        anexo_b = adicionar_anexo(item_b["id"], PNG_BYTES, "image/png", "x.png")
        _login_as_aluno(monkeypatch, aluno_a["id"])

        response = client.post(
            f"/aluno/anexos/{anexo_b['id']}/remover", follow_redirects=False
        )

    assert response.status_code == 404
    assert get_anexo(anexo_b["id"]) is not None
    assert (kairos.config.anexos_dir() / anexo_b["filename"]).exists()


def test_post_remover_unknown_anexo_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        aluno, _, _ = _setup()
        _login_as_aluno(monkeypatch, aluno["id"])
        response = client.post("/aluno/anexos/999999/remover", follow_redirects=False)

    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# 4. Coach route                                                              #
# --------------------------------------------------------------------------- #


def test_coach_serves_own_alunos_anexo(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno, _, item = _setup()
        anexo = adicionar_anexo(item["id"], MP4_BYTES, "video/mp4", "x.mp4")

        response = client.get(f"/alunos/{aluno['id']}/anexos/{anexo['id']}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == MP4_BYTES


def test_coach_anexo_of_different_aluno_than_url_returns_404(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno_a, _, _ = _setup("Aluno A")
        _, _, item_b = _setup("Aluno B")
        anexo_b = adicionar_anexo(item_b["id"], PNG_BYTES, "image/png", "x.png")

        response = client.get(f"/alunos/{aluno_a['id']}/anexos/{anexo_b['id']}")

    assert response.status_code == 404


def test_coach_anexo_unknown_anexo_or_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno, _, item = _setup()
        anexo = adicionar_anexo(item["id"], PNG_BYTES, "image/png", "x.png")

        unknown_anexo = client.get(f"/alunos/{aluno['id']}/anexos/999999")
        unknown_aluno = client.get(f"/alunos/999999/anexos/{anexo['id']}")

    assert unknown_anexo.status_code == 404
    assert unknown_aluno.status_code == 404


def test_coach_anexo_orphan_file_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno, _, item = _setup()
        anexo = adicionar_anexo(item["id"], PNG_BYTES, "image/png", "x.png")
        (kairos.config.anexos_dir() / anexo["filename"]).unlink()

        response = client.get(f"/alunos/{aluno['id']}/anexos/{anexo['id']}")

    assert response.status_code == 404


def test_coach_planilha_lists_anexo_with_coach_url_and_observacao(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno, treino, item = _setup()
        anexo = adicionar_anexo(
            item["id"], PNG_BYTES, "image/png", "x.png", observacao="Olha isso"
        )

        page = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert page.status_code == 200
    assert f"/alunos/{aluno['id']}/anexos/{anexo['id']}" in page.text
    assert "Olha isso" in page.text
