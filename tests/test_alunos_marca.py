"""Tests for issue 03: brand visuals for Alunos (Alunos no visual da marca).

Covers the functional specification:
- the design system stylesheet (/static/css/components.css) is served and
  the /alunos page links to it in a <link> tag;
- a student whose optional fields are all empty renders "sem registro" for
  every one of them wrapped in an element with class "none": the 9
  pre-existing fields (birth date, age, objective, phase, plan start, plan
  end, restrictions, alert and notes) plus the 7 added by issue 23 (contact,
  sex, age_reported, weekly_frequency, health_conditions, medications,
  conditioning_level) -> 16 fields, architecture rule 6;
- the list card's status badge carries the status-specific CSS class
  (badge-active for an active student).

Same isolation pattern as tests/test_lista_alunos.py: KAIROS_DATA_DIR
points at a temp dir and the cached engine is disposed on teardown.
"""

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


def test_components_css_is_served(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/static/css/components.css")

    assert response.status_code == 200


def test_alunos_page_links_components_css(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos")

    assert response.status_code == 200
    assert re.search(
        r'<link[^>]+href="/static/css/components\.css\?v=', response.text
    ), "the alunos page should link to /static/css/components.css"


def test_profile_empty_fields_wrapped_in_none_class(data_dir: Path) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data={"name": "Maria Silva"}, follow_redirects=False)
        lista = client.get("/alunos")
        match = re.search(r'href="(/alunos/\d+)"', lista.text)
        assert match is not None
        response = client.get(match.group(1))

    assert response.status_code == 200
    # Every "sem registro" value for an optional field must be inside an
    # element carrying class="none": the 9 pre-existing fields (birth date,
    # age, objective, phase, plan start, plan end, restrictions, alert,
    # notes) plus the 7 added by issue 23 (contact, sex, age_reported,
    # weekly_frequency, health_conditions, medications, conditioning_level)
    # plus email added by issue 29 -> 17 fields.
    none_values = re.findall(
        r'<span class="none">([^<]*)</span>', response.text
    )
    assert len(none_values) == 17
    assert all(value.strip() == "sem registro" for value in none_values)


def test_list_card_badge_has_status_class(data_dir: Path) -> None:
    with TestClient(app) as client:
        client.post("/alunos", data={"name": "Maria Silva"}, follow_redirects=False)
        response = client.get("/alunos")

    assert response.status_code == 200
    assert re.search(
        r'<span class="badge badge-active">', response.text
    ), "an active student's badge should carry the badge-active class"
