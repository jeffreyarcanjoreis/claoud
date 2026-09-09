"""Tests for issue 03: student list (lista de alunos).

Covers the functional specification:
- GET /alunos with no students returns 200 with "Nenhum aluno cadastrado.";
- GET / renders the Início page (200), not a redirect (issue 05);
- full flow: POST /alunos creates a student, following the redirect lands on
  the list (200) with the success message and the student's name in a card;
- a student with objective and plan period shows name, objective, "Ativo"
  status badge and the period formatted "DD/MM/AAAA → DD/MM/AAAA";
- a student without objective and without plan dates shows "sem registro"
  for both objective and period (architecture rule 6);
- a student with only plan_start shows the formatted start date and
  "sem registro" in place of the end date;
- students are ordered by name case-insensitively ("Ana Lima" before
  "bruno costa");
- the list page links to /alunos/novo ("Novo aluno") and the new-student
  page links back to the list ("Voltar para a lista").

Same isolation pattern as tests/test_cadastro_aluno.py: KAIROS_DATA_DIR
points at a temp dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_empty_list_shows_nenhum_aluno_cadastrado(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200
    assert "Nenhum aluno cadastrado." in response.text


def test_root_renders_inicio_not_a_redirect(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert "Visão geral" in response.text


def test_full_flow_create_then_list_shows_message_and_card(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos",
            data={"name": "Maria Silva"},
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert "cadastrado" in response.text  # success message on the list page
    assert "Maria Silva" in response.text  # student's name in a card
    assert "card" in response.text  # rendered inside a card element


def test_card_shows_name_objective_status_and_period(data_dir: Path) -> None:
    with TestClient(app) as client:
        client.post(
            "/alunos",
            data={
                "name": "Maria Silva",
                "objective": "Hipertrofia geral",
                "plan_start": "2024-01-02",
                "plan_end": "2024-02-15",
            },
            follow_redirects=False,
        )
        response = client.get("/alunos")

    assert response.status_code == 200
    assert "Maria Silva" in response.text
    assert "Hipertrofia geral" in response.text
    assert "Ativo" in response.text
    assert "02/01/2024 → 15/02/2024" in response.text


def test_card_without_objective_and_dates_shows_sem_registro(data_dir: Path) -> None:
    with TestClient(app) as client:
        client.post(
            "/alunos",
            data={"name": "Maria Silva", "objective": "", "plan_start": "", "plan_end": ""},
            follow_redirects=False,
        )
        response = client.get("/alunos")

    assert response.status_code == 200
    assert "Maria Silva" in response.text
    # Both the objective and the period fall back to "sem registro".
    assert response.text.count("sem registro") >= 2


def test_card_with_only_plan_start_shows_date_and_sem_registro_end(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        client.post(
            "/alunos",
            data={"name": "Maria Silva", "plan_start": "2024-01-02", "plan_end": ""},
            follow_redirects=False,
        )
        response = client.get("/alunos")

    assert response.status_code == 200
    assert "02/01/2024" in response.text
    assert "02/01/2024 → sem registro" in response.text


def test_list_is_ordered_by_name_case_insensitive(data_dir: Path) -> None:
    with TestClient(app) as client:
        # Inserted out of order and with mixed case on purpose.
        client.post("/alunos", data={"name": "bruno costa"}, follow_redirects=False)
        client.post("/alunos", data={"name": "Ana Lima"}, follow_redirects=False)
        response = client.get("/alunos")

    assert response.status_code == 200
    ana_position = response.text.index("Ana Lima")
    bruno_position = response.text.index("bruno costa")
    assert ana_position < bruno_position


def test_list_links_to_novo_and_novo_links_back_to_list(data_dir: Path) -> None:
    with TestClient(app) as client:
        lista = client.get("/alunos")
        novo = client.get("/alunos/novo")

    assert lista.status_code == 200
    assert 'href="/alunos/novo"' in lista.text
    assert "Novo aluno" in lista.text

    assert novo.status_code == 200
    assert 'href="/alunos"' in novo.text
    assert "Voltar para a lista" in novo.text
