"""Tests for issue 15: read-only session arc on the student's workout page."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.treinos.service import create_treino, set_duracao

FASES_ORDEM = ["Preparação", "Aquecimento", "Skill", "Ápice", "Volta à calma"]


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


def _minutes(html: str) -> list[int]:
    return [int(m) for m in re.findall(r'class="arco-fase-min">(\d+) min<', html)]


def _names(html: str) -> list[str]:
    return re.findall(r'class="arco-fase-nome">([^<]+)<', html)


def _setup(monkeypatch: pytest.MonkeyPatch, duracao=None):
    aluno = create_aluno(name="Ana")
    treino = create_treino(aluno["id"], nome="Treino A")
    if duracao is not None:
        set_duracao(treino["id"], duracao)
    _login_as_aluno(monkeypatch, aluno["id"])
    return aluno, treino


def test_aluno_sees_arco_with_minutes_for_45(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _, treino = _setup(monkeypatch, 45)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.status_code == 200
    assert 'class="arco"' in page.text
    assert _names(page.text) == FASES_ORDEM
    assert _minutes(page.text) == [4, 7, 11, 16, 7]
    assert "16 min" in page.text and "4 min" in page.text
    assert "Este corpo está pronto?" in page.text


def test_arco_sits_before_progresso(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _, treino = _setup(monkeypatch, 45)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    if "progresso" in page.text:
        assert page.text.index('class="arco"') < page.text.index("progresso")


def test_changing_duracao_to_60_updates_aluno_arco(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _, treino = _setup(monkeypatch, 45)
        set_duracao(treino["id"], 60)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert _minutes(page.text) == [5, 9, 15, 22, 9]
    assert "22 min" in page.text
    assert "16 min" not in page.text


def test_arco_proportional_widths(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _, treino = _setup(monkeypatch, 30)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert _minutes(page.text) == [3, 5, 7, 10, 5]
    assert re.findall(r'class="arco-fase"[^>]*style="flex: (\d+)"', page.text) == [
        "3", "5", "7", "10", "5",
    ]


def test_treino_without_duracao_has_no_arco_nor_invite(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _, treino = _setup(monkeypatch)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.status_code == 200
    assert 'class="arco"' not in page.text
    assert _minutes(page.text) == []
    assert "Defina a duração" not in page.text
    assert "arco da sessão" not in page.text.lower().replace("aria-label", "")


def test_clearing_duracao_removes_aluno_arco(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _, treino = _setup(monkeypatch, 45)
        set_duracao(treino["id"], None)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert 'class="arco"' not in page.text


@pytest.mark.parametrize("duracao", [None, 45])
def test_aluno_page_has_no_duration_selector_or_form(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch, duracao
) -> None:
    with TestClient(app) as client:
        _, treino = _setup(monkeypatch, duracao)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert "/duracao" not in page.text
    assert "Duração da sessão" not in page.text
    assert "sem arco" not in page.text
    assert 'name="duracao"' not in page.text
    assert "duracao-opcao" not in page.text


def test_arco_strip_is_not_inside_a_form(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        _, treino = _setup(monkeypatch, 45)
        page = client.get(f"/aluno/treinos/{treino['id']}")

    start = page.text.index('class="arco"')
    end = page.text.index("arco-fase-min", start)
    segment = page.text[start:end]
    assert "<form" not in segment and "<button" not in segment


def test_another_alunos_treino_returns_404(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(app) as client:
        dono = create_aluno(name="Dono")
        outro = create_aluno(name="Outro")
        treino = create_treino(dono["id"], nome="Treino do Dono")
        set_duracao(treino["id"], 45)
        _login_as_aluno(monkeypatch, outro["id"])
        page = client.get(f"/aluno/treinos/{treino['id']}")

    assert page.status_code == 404
    assert "arco-fase" not in page.text
