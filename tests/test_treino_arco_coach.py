"""Tests for issue 14: session arc on the coach's planilha.

- POST /alunos/{aluno_id}/treino/{treino_id}/duracao (form ``duracao``)
  sets/clears the session duration and redirects (303) to the planilha.
- The planilha shows the duration selector (active one highlighted) and, when
  a duration is set, the ``.arco`` strip with the 5 phases in canonical order
  and the proportional minutes; otherwise only the invitation to set it.
- Tampered durations are a no-op; another student's workout -> 404.

Isolation: KAIROS_DATA_DIR points at a tmp_path; conftest auto-logs in as coach.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.treinos.service import create_treino, get_treino

CONVITE = "Defina a duração para ver o arco da sessão."
ARCO_DIV = 'class="arco"'
FASES_ORDEM = ["Preparação", "Aquecimento", "Skill", "Ápice", "Volta à calma"]


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def _arco_minutes(html: str) -> list[int]:
    return [int(m) for m in re.findall(r'class="arco-fase-min">(\d+) min<', html)]


def _arco_names(html: str) -> list[str]:
    return re.findall(r'class="arco-fase-nome">([^<]+)<', html)


def _post_duracao(client: TestClient, aluno_id: int, treino_id: int, value: str):
    return client.post(
        f"/alunos/{aluno_id}/treino/{treino_id}/duracao",
        data={"duracao": value},
        follow_redirects=False,
    )


def _active_buttons(html: str) -> list[str]:
    return re.findall(r'class="duracao-opcao is-ativa"[^>]*>(\d+) min<', html)


# --------------------------------------------------------------------------- #
# 1. Set duration -> arc visible                                              #
# --------------------------------------------------------------------------- #

def test_post_duracao_45_redirects_and_planilha_shows_arco(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        url = f"/alunos/{aluno['id']}/treino/{treino['id']}"

        response = _post_duracao(client, aluno["id"], treino["id"], "45")
        assert response.status_code == 303
        assert response.headers["location"] == url

        page = client.get(url)

    assert page.status_code == 200
    assert get_treino(treino["id"])["duracao_min"] == 45
    assert ARCO_DIV in page.text
    assert CONVITE not in page.text
    assert _arco_minutes(page.text) == [4, 7, 11, 16, 7]
    assert "16 min" in page.text and "4 min" in page.text
    assert _active_buttons(page.text) == ["45"]


def test_arco_segments_follow_canonical_phase_order(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        _post_duracao(client, aluno["id"], treino["id"], "60")
        page = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert _arco_names(page.text) == FASES_ORDEM
    assert _arco_minutes(page.text) == [5, 9, 15, 22, 9]
    assert sum(_arco_minutes(page.text)) == 60
    # proportional widths
    assert re.findall(r'class="arco-fase"[^>]*style="flex: (\d+)"', page.text) == [
        "5", "9", "15", "22", "9",
    ]
    # guiding question is shown inside the arc
    assert "Este corpo está pronto?" in page.text


# --------------------------------------------------------------------------- #
# 2. Change duration                                                          #
# --------------------------------------------------------------------------- #

def test_changing_duracao_to_30_updates_arco_minutes(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        url = f"/alunos/{aluno['id']}/treino/{treino['id']}"
        _post_duracao(client, aluno["id"], treino["id"], "45")
        response = _post_duracao(client, aluno["id"], treino["id"], "30")
        assert response.status_code == 303
        page = client.get(url)

    assert get_treino(treino["id"])["duracao_min"] == 30
    assert _arco_minutes(page.text) == [3, 5, 7, 10, 5]
    assert "10 min" in page.text
    assert "16 min" not in page.text
    assert _active_buttons(page.text) == ["30"]


# --------------------------------------------------------------------------- #
# 3. Clear duration                                                           #
# --------------------------------------------------------------------------- #

def test_clearing_duracao_removes_arco_and_shows_convite(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        url = f"/alunos/{aluno['id']}/treino/{treino['id']}"
        _post_duracao(client, aluno["id"], treino["id"], "45")
        response = _post_duracao(client, aluno["id"], treino["id"], "")
        assert response.status_code == 303
        page = client.get(url)

    assert get_treino(treino["id"])["duracao_min"] is None
    assert CONVITE in page.text
    assert ARCO_DIV not in page.text
    assert _arco_minutes(page.text) == []
    assert _active_buttons(page.text) == []


# --------------------------------------------------------------------------- #
# 4. Tampered value                                                           #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("bad", ["50", "abc", "-30", "0", "45.5"])
def test_tampered_duracao_is_noop_and_keeps_previous_value(
    data_dir: Path, bad: str
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        _post_duracao(client, aluno["id"], treino["id"], "45")

        response = _post_duracao(client, aluno["id"], treino["id"], bad)
        assert response.status_code == 303
        page = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert get_treino(treino["id"])["duracao_min"] == 45
    assert _arco_minutes(page.text) == [4, 7, 11, 16, 7]


def test_tampered_duracao_on_treino_without_duration_stays_empty(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        response = _post_duracao(client, aluno["id"], treino["id"], "50")
        assert response.status_code == 303
        page = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert get_treino(treino["id"])["duracao_min"] is None
    assert CONVITE in page.text
    assert ARCO_DIV not in page.text


# --------------------------------------------------------------------------- #
# 5. 404 guards                                                               #
# --------------------------------------------------------------------------- #

def test_post_duracao_404_for_another_alunos_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        dono = create_aluno(name="Dono")
        outro = create_aluno(name="Outro")
        treino = create_treino(dono["id"], nome="Treino do Dono")
        response = _post_duracao(client, outro["id"], treino["id"], "45")

    assert response.status_code == 404
    assert get_treino(treino["id"])["duracao_min"] is None


def test_post_duracao_404_for_missing_treino(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        response = _post_duracao(client, aluno["id"], 9999, "45")
    assert response.status_code == 404


def test_post_duracao_404_for_missing_aluno(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        response = _post_duracao(client, 9999, treino["id"], "45")
    assert response.status_code == 404
    assert get_treino(treino["id"])["duracao_min"] is None


# --------------------------------------------------------------------------- #
# 6. No duration (new workout)                                                #
# --------------------------------------------------------------------------- #

def test_new_treino_without_duracao_shows_convite_and_no_arco(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        page = client.get(f"/alunos/{aluno['id']}/treino/{treino['id']}")

    assert page.status_code == 200
    assert "Duração da sessão" in page.text
    assert CONVITE in page.text
    assert ARCO_DIV not in page.text
    assert _arco_minutes(page.text) == []
    assert _active_buttons(page.text) == []
    # selector offers the three options
    for d in (30, 45, 60):
        assert f'name="duracao" value="{d}"' in page.text
