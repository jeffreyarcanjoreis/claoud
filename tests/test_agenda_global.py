"""Tests for issue 06 (agenda global de hoje + tile do Início).

Covers the functional specification:
- with no sessions scheduled for today, GET /agenda shows the empty state
  ("Nenhuma sessão hoje.");
- with 2 sessions scheduled for TODAY from different students, GET /agenda
  shows both students' names, hours and types, in hour order (earliest
  first), each one linking to /alunos/{aluno_id}/agenda;
- a session scheduled for another day does not show up in GET /agenda;
- the Início's "Sessões de hoje" tile shows the real count (not "em breve")
  and links to /agenda.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

import datetime
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.agenda.service import create_sessao
from kairos.alunos.service import create_aluno
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_no_sessions_today_shows_empty_state(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/agenda")

    assert response.status_code == 200
    assert "Nenhuma sessão hoje." in response.text


def test_two_sessions_today_show_name_hora_tipo_in_hour_order_and_link(
    data_dir: Path,
) -> None:
    hoje = datetime.date.today().isoformat()

    with TestClient(app) as client:
        early_aluno = create_aluno(name="Ana Early")
        late_aluno = create_aluno(name="Bruno Late")

        create_sessao(
            late_aluno["id"], data=hoje, hora="10:00", tipo="grupo"
        )
        create_sessao(
            early_aluno["id"], data=hoje, hora="08:00", tipo="individual"
        )

        response = client.get("/agenda")

    assert response.status_code == 200
    text = response.text

    assert "Ana Early" in text
    assert "Bruno Late" in text
    assert "08:00" in text
    assert "10:00" in text
    assert "Individual" in text
    assert "Grupo" in text

    assert f'href="/alunos/{early_aluno["id"]}/agenda"' in text
    assert f'href="/alunos/{late_aluno["id"]}/agenda"' in text

    early_pos = text.index("Ana Early")
    late_pos = text.index("Bruno Late")
    assert early_pos < late_pos, (
        "the earliest-hour session's student should appear before the later"
        " one in the HTML"
    )


def test_session_from_another_day_does_not_appear_in_todays_agenda(
    data_dir: Path,
) -> None:
    hoje = datetime.date.today().isoformat()
    outro_dia = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()

    with TestClient(app) as client:
        aluno_hoje = create_aluno(name="Carla Hoje")
        aluno_futuro = create_aluno(name="Diego Futuro")

        create_sessao(aluno_hoje["id"], data=hoje, hora="09:00", tipo="individual")
        create_sessao(aluno_futuro["id"], data=outro_dia, hora="14:00", tipo="grupo")

        response = client.get("/agenda")

    assert response.status_code == 200
    text = response.text

    assert "Carla Hoje" in text
    assert "Diego Futuro" not in text


def test_inicio_tile_shows_real_count_and_links_to_agenda(data_dir: Path) -> None:
    hoje = datetime.date.today().isoformat()

    with TestClient(app) as client:
        aluno_a = create_aluno(name="Elisa Um")
        aluno_b = create_aluno(name="Fabio Dois")
        create_sessao(aluno_a["id"], data=hoje, hora="08:00", tipo="individual")
        create_sessao(aluno_b["id"], data=hoje, hora="09:00", tipo="grupo")

        response = client.get("/")

    assert response.status_code == 200
    text = response.text

    assert '<a class="stat" href="/agenda">' in text
    assert "<div class=\"n\">2</div>" in text

    tile_match = re.search(
        r'<a class="stat" href="/agenda">(.*?)</a>', text, re.DOTALL
    )
    assert tile_match is not None, "the Início page should have the sessões-hoje tile"
    assert "em breve" not in tile_match.group(1)


def test_inicio_tile_shows_zero_when_no_sessions_today(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    text = response.text

    assert '<a class="stat" href="/agenda">' in text
    assert "<div class=\"n\">0</div>" in text

    tile_match = re.search(
        r'<a class="stat" href="/agenda">(.*?)</a>', text, re.DOTALL
    )
    assert tile_match is not None, "the Início page should have the sessões-hoje tile"
    assert "em breve" not in tile_match.group(1)
