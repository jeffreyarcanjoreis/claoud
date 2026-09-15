"""Tests for issues 04 (perfil do aluno) and 05 (idade derivada).

Covers the functional specification:
- GET /alunos/{id} shows the full profile: every filled field appears
  (name, objective, phase, dates as DD/MM/AAAA, restrictions, alert,
  notes) plus the status badge;
- a student with only a name shows "sem registro" for every empty field
  (birth date, age, objective, phase, plan start, plan end, restrictions,
  alert, notes — architecture rule 6);
- the age is derived from birth_date on the server: correct both when the
  birthday already happened this year and when it has not (dates computed
  dynamically from date.today() so the test never rots);
- no birth date -> "Idade:" line falls back to "sem registro";
- unknown id -> 404 with "Aluno não encontrado.";
- /alunos/novo still answers 200 (the literal route is not swallowed by
  the parameterized /alunos/{aluno_id});
- the list card links to the profile (href="/alunos/{id}") and the profile
  links back to the list (href="/alunos").

Same isolation pattern as tests/test_lista_alunos.py: KAIROS_DATA_DIR
points at a temp dir and the cached engine is disposed on teardown.
"""

import datetime
import re
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


def _create_and_get_profile(client: TestClient, data: dict) -> "object":
    """POST a student, then GET its profile via the link on the list page."""
    client.post("/alunos", data=data, follow_redirects=False)
    lista = client.get("/alunos")
    match = re.search(r'href="(/alunos/\d+)"', lista.text)
    assert match is not None, "list card should link to the profile"
    return client.get(match.group(1))


def test_full_profile_shows_every_field_and_status_badge(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = _create_and_get_profile(
            client,
            {
                "name": "Maria Silva",
                "birth_date": "1990-03-15",
                "objective": "Hipertrofia geral",
                "phase": "Adaptação",
                "plan_start": "2024-01-02",
                "plan_end": "2024-02-15",
                "restrictions": "Condromalácia patelar",
                "alert": "Evitar impacto no joelho",
                "notes": "Prefere treinar de manhã",
            },
        )

    assert response.status_code == 200
    assert "Maria Silva" in response.text
    assert "Hipertrofia geral" in response.text
    assert "Adaptação" in response.text
    # Dates formatted server-side as DD/MM/AAAA.
    assert "15/03/1990" in response.text
    assert "02/01/2024" in response.text
    assert "15/02/2024" in response.text
    assert "Condromalácia patelar" in response.text
    assert "Evitar impacto no joelho" in response.text
    assert "Prefere treinar de manhã" in response.text
    # Status badge (default status is active -> "Ativo").
    assert "Ativo" in response.text
    assert "badge" in response.text


def test_profile_with_only_name_shows_sem_registro_for_empty_fields(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = _create_and_get_profile(client, {"name": "Maria Silva"})

    assert response.status_code == 200
    assert "Maria Silva" in response.text
    # Empty fields: birth date, age, objective, phase, plan start, plan end,
    # restrictions, alert and notes all fall back to "sem registro".
    assert response.text.count("sem registro") >= 8


def test_age_when_birthday_already_happened_this_year(data_dir: Path) -> None:
    # Birthday was yesterday (month/day-wise), 30 years ago -> exactly 30.
    anchor = datetime.date.today() - datetime.timedelta(days=1)
    try:
        birth = anchor.replace(year=anchor.year - 30)
    except ValueError:  # anchor is Feb 29 and target year is not leap
        birth = anchor.replace(year=anchor.year - 30, day=28)

    with TestClient(app) as client:
        response = _create_and_get_profile(
            client, {"name": "Maria Silva", "birth_date": birth.isoformat()}
        )

    assert response.status_code == 200
    assert "Idade" in response.text
    assert "30 anos" in response.text


def test_age_when_birthday_has_not_happened_yet_this_year(data_dir: Path) -> None:
    # Birthday is tomorrow (month/day-wise), born 30 calendar years before
    # -> still 29 today.
    anchor = datetime.date.today() + datetime.timedelta(days=1)
    try:
        birth = anchor.replace(year=anchor.year - 30)
    except ValueError:  # anchor is Feb 29 and target year is not leap
        birth = datetime.date(anchor.year - 30, 3, 1)

    with TestClient(app) as client:
        response = _create_and_get_profile(
            client, {"name": "Maria Silva", "birth_date": birth.isoformat()}
        )

    assert response.status_code == 200
    assert "Idade" in response.text
    assert "29 anos" in response.text
    assert "30 anos" not in response.text


def test_profile_without_birth_date_shows_idade_sem_registro(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = _create_and_get_profile(
            client,
            {
                "name": "Maria Silva",
                "birth_date": "",
                "objective": "Hipertrofia geral",
            },
        )

    assert response.status_code == 200
    assert "Idade" in response.text
    # The "Idade" row falls back to "sem registro" (no invented value).
    # Markup is <dt class="k">Idade</dt> ... <dd class="v"><span class="none">
    # sem registro</span></dd>; assert on the text, tolerant of the tags.
    idade_row = re.search(
        r"<dt[^>]*>Idade</dt>\s*<dd[^>]*>(.*?)</dd>", response.text, re.DOTALL
    )
    assert idade_row is not None
    row_text = re.sub(r"<[^>]+>", "", idade_row.group(1)).strip()
    assert row_text == "sem registro"
    assert "anos" not in row_text


def test_unknown_id_returns_404_aluno_nao_encontrado(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_alunos_novo_still_returns_200_not_swallowed_by_id_route(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/novo")

    assert response.status_code == 200
    assert "Novo aluno" in response.text


def test_list_card_links_to_profile(data_dir: Path) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data={"name": "Maria Silva"}, follow_redirects=False)
        lista = client.get("/alunos")

    assert lista.status_code == 200
    match = re.search(r'href="/alunos/(\d+)"', lista.text)
    assert match is not None, 'list card should carry href="/alunos/{id}"'


def test_profile_links_back_to_list(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = _create_and_get_profile(client, {"name": "Maria Silva"})

    assert response.status_code == 200
    assert 'href="/alunos"' in response.text
    assert "Voltar para a lista" in response.text


# ---------------------------------------------------------------------------
# issue 23: expanded profile fields (contact, sex, age_reported,
# weekly_frequency, conditioning_level, health_conditions, medications)
# ---------------------------------------------------------------------------


def test_profile_shows_the_expanded_fields_when_filled(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = _create_and_get_profile(
            client,
            {
                "name": "Maria Silva",
                "contact": "(11) 99999-0000",
                "sex": "feminino",
                "age_reported": "34",
                "weekly_frequency": "3-4",
                "conditioning_level": "iniciante",
                "health_conditions": "Hipertensão controlada",
                "medications": "Losartana",
            },
        )

    assert response.status_code == 200
    body = response.text
    assert "(11) 99999-0000" in body
    assert "Feminino" in body
    assert "34 anos" in body
    assert "3 a 4 dias" in body
    assert "Iniciante" in body
    assert "Hipertensão controlada" in body
    assert "Losartana" in body


def test_profile_shows_sem_registro_for_empty_expanded_fields(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = _create_and_get_profile(client, {"name": "Maria Silva"})

    assert response.status_code == 200
    # 16 fields can fall back to "sem registro" on a name-only profile: the
    # 9 pre-existing ones (birth date, age, objective, phase, plan start,
    # plan end, restrictions, alert, notes) plus the 7 added by issue 23
    # (contact, sex, age_reported, weekly_frequency, health_conditions,
    # medications, conditioning_level).
    assert response.text.count("sem registro") >= 15


def test_profile_shows_contact_row_label(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = _create_and_get_profile(client, {"name": "Maria Silva"})

    assert response.status_code == 200
    assert "Contato" in response.text
    assert "Sexo" in response.text
    assert "Frequência semanal" in response.text
    assert "Nível de condicionamento" in response.text
    assert "Condições / patologias" in response.text
    assert "Medicamentos" in response.text
