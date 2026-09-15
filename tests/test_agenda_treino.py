"""Tests for linking a treino to an agenda session (slice 9.3).

- service: create_sessao accepts an optional treino_id, validates it belongs to
  the same student, and list_sessoes / sessoes_de_hoje carry the treino name.
- routes: the "Agendar sessão" form offers the student's treinos; scheduling
  with a treino shows it (with a "ver treino" link) on the student's agenda and
  on the global today agenda.

Isolation pattern shared with the other suites.
"""

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.agenda.service import (
    ValidationError,
    create_sessao,
    list_sessoes,
    sessoes_de_hoje,
)
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.treinos.service import create_treino


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


# --------------------------------------------------------------------------- #
# service                                                                      #
# --------------------------------------------------------------------------- #

def test_create_sessao_links_treino(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino A")
        sessao = create_sessao(
            aluno["id"],
            data="2026-09-01",
            hora="08:00",
            tipo="individual",
            treino_id=str(treino["id"]),
        )
        assert sessao["treino_id"] == treino["id"]


def test_create_sessao_without_treino_is_null(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        sessao = create_sessao(
            aluno["id"], data="2026-09-01", hora="08:00", tipo="individual"
        )
        assert sessao["treino_id"] is None


def test_create_sessao_rejects_treino_of_another_aluno(data_dir: Path) -> None:
    with TestClient(app):
        dono = create_aluno(name="Dono")
        outro = create_aluno(name="Outro")
        treino = create_treino(dono["id"], nome="Treino do Dono")
        with pytest.raises(ValidationError):
            create_sessao(
                outro["id"],
                data="2026-09-01",
                hora="08:00",
                tipo="individual",
                treino_id=str(treino["id"]),
            )


def test_create_sessao_rejects_invalid_treino_id(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        with pytest.raises(ValidationError):
            create_sessao(
                aluno["id"],
                data="2026-09-01",
                hora="08:00",
                tipo="individual",
                treino_id="abc",
            )


def test_list_and_today_carry_treino_name(data_dir: Path) -> None:
    hoje = datetime.date.today().isoformat()
    with TestClient(app):
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino Peito")
        create_sessao(
            aluno["id"], data=hoje, hora="08:00", tipo="individual",
            treino_id=str(treino["id"]),
        )

        sessoes = list_sessoes(aluno["id"])
        assert sessoes[0]["treino_nome"] == "Treino Peito"

        hoje_list = sessoes_de_hoje()
        assert hoje_list[0]["treino_nome"] == "Treino Peito"


# --------------------------------------------------------------------------- #
# routes                                                                       #
# --------------------------------------------------------------------------- #

def test_nova_form_offers_the_alunos_treinos(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        create_treino(aluno["id"], nome="Treino Especial")
        response = client.get(f"/alunos/{aluno['id']}/agenda/nova")

    assert response.status_code == 200
    assert 'name="treino_id"' in response.text
    assert "Treino Especial" in response.text


def test_schedule_with_treino_shows_link_on_agenda(data_dir: Path) -> None:
    hoje = datetime.date.today().isoformat()
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino Ligado")

        created = client.post(
            f"/alunos/{aluno['id']}/agenda",
            data={
                "data": hoje,
                "hora": "08:00",
                "tipo": "individual",
                "treino_id": str(treino["id"]),
            },
            follow_redirects=False,
        )
        assert created.status_code == 303

        agenda = client.get(f"/alunos/{aluno['id']}/agenda")

    assert "Treino Ligado" in agenda.text
    assert f'href="/alunos/{aluno["id"]}/treino/{treino["id"]}"' in agenda.text


def test_global_today_agenda_shows_treino_link(data_dir: Path) -> None:
    hoje = datetime.date.today().isoformat()
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana")
        treino = create_treino(aluno["id"], nome="Treino Hoje")
        create_sessao(
            aluno["id"], data=hoje, hora="08:00", tipo="individual",
            treino_id=str(treino["id"]),
        )

        response = client.get("/agenda")

    assert "Treino Hoje" in response.text
    assert f'href="/alunos/{aluno["id"]}/treino/{treino["id"]}"' in response.text
