"""Tests for the biblioteca de exercícios (slice 9.1): service + routes.

- service: create validates the required name, empty optional fields become
  None (rule 6), listing is ordered case-insensitively by name, counting;
- routes: empty state, the new-exercise form, creating via POST (redirect and
  then visible in the list), rejecting a blank name (400 + preserved values),
  and the "Treinos" navigation tab.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.main import app
from kairos.treinos.service import (
    ValidationError,
    count_exercicios,
    create_exercicio,
    list_exercicios,
)


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

def test_create_exercicio_persists_and_returns_fields(data_dir: Path) -> None:
    with TestClient(app):  # triggers migrations via lifespan
        result = create_exercicio(
            nome="Supino reto", grupo_muscular="Peito", observacao="barra"
        )
        assert result["id"] is not None
        assert result["nome"] == "Supino reto"
        assert result["grupo_muscular"] == "Peito"
        assert result["observacao"] == "barra"
        assert count_exercicios() == 1


def test_create_exercicio_empty_optionals_become_none(data_dir: Path) -> None:
    with TestClient(app):
        result = create_exercicio(nome="Prancha", grupo_muscular="   ", observacao="")
        assert result["grupo_muscular"] is None
        assert result["observacao"] is None


def test_create_exercicio_without_nome_raises(data_dir: Path) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            create_exercicio(nome="   ")
        assert count_exercicios() == 0


def test_list_exercicios_is_ordered_case_insensitively(data_dir: Path) -> None:
    with TestClient(app):
        create_exercicio(nome="banco")
        create_exercicio(nome="Agachamento")
        create_exercicio(nome="Zerchers")
        nomes = [e["nome"] for e in list_exercicios()]
    assert nomes == ["Agachamento", "banco", "Zerchers"]


# --------------------------------------------------------------------------- #
# routes                                                                       #
# --------------------------------------------------------------------------- #

def test_treinos_empty_state(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/treinos")
    assert response.status_code == 200
    assert "Biblioteca de exercícios" in response.text
    assert "Ainda não há exercícios" in response.text


def test_new_exercicio_form_renders(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/treinos/novo")
    assert response.status_code == 200
    assert 'name="nome"' in response.text
    assert 'name="grupo_muscular"' in response.text


def test_post_creates_exercicio_and_shows_in_list(data_dir: Path) -> None:
    with TestClient(app) as client:
        created = client.post(
            "/treinos",
            data={"nome": "Levantamento terra", "grupo_muscular": "Posterior"},
            follow_redirects=False,
        )
        assert created.status_code == 303
        assert created.headers["location"] == "/treinos"

        listed = client.get("/treinos")

    assert "Levantamento terra" in listed.text
    assert "Posterior" in listed.text


def test_post_without_nome_is_rejected_and_preserves_values(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/treinos",
            data={"nome": "", "grupo_muscular": "Peito"},
            follow_redirects=False,
        )
    assert response.status_code == 400
    assert "Nome é obrigatório." in response.text
    # the typed group is preserved so the coach doesn't retype it
    assert 'value="Peito"' in response.text


def test_treinos_nav_tab_present(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/treinos")
    assert 'href="/treinos">Treinos</a>' in response.text
