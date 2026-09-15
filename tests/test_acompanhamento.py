"""Tests for issue 13 (Acompanhamento -- sessão realizada).

Covers the functional specification:
- service: data and presença are required (ValidationError when missing);
  an invalid presença or disposição value is rejected; an empty disposição
  normalizes to None; a valid registro is created and persisted;
  list_sessoes_realizadas returns registros ordered by data descending;
- routes: the "Acompanhamento" sub-tab shows an empty-state message when the
  student has no registros; an unknown aluno id -> 404; the new-registro form
  shows the presença and disposição fields; a valid POST creates the
  registro and redirects (303) to the list, where it appears; a POST without
  presença -> 400 with the error message and the submitted values preserved;
  removing a registro takes it out of the list and redirects (303); removing
  a registro that belongs to another student via the wrong URL -> 404; the
  "Acompanhamento" sub-tab is present in the ficha and carries no "em breve"
  marker.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.acompanhamento.service import (
    ValidationError,
    create_sessao_realizada,
    list_sessoes_realizadas,
)
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


# --- service layer -----------------------------------------------------


def test_create_without_data_raises_validation_error(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            create_sessao_realizada(aluno["id"], presenca="compareceu")


def test_create_without_presenca_raises_validation_error(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            create_sessao_realizada(aluno["id"], data="2026-09-01")


def test_create_invalid_presenca_raises_validation_error(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            create_sessao_realizada(
                aluno["id"], data="2026-09-01", presenca="xpto"
            )


def test_create_invalid_disposicao_raises_validation_error(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            create_sessao_realizada(
                aluno["id"],
                data="2026-09-01",
                presenca="compareceu",
                disposicao="altíssima",
            )


def test_create_empty_disposicao_normalizes_to_none(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        registro = create_sessao_realizada(
            aluno["id"], data="2026-09-01", presenca="compareceu", disposicao=""
        )

    assert registro["disposicao"] is None


def test_create_valid_registro_persists(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        registro = create_sessao_realizada(
            aluno["id"],
            data="2026-09-01",
            presenca="compareceu",
            disposicao="boa",
            feedback="Foi muito bem hoje.",
        )

        registros = list_sessoes_realizadas(aluno["id"])

    assert registro["data"].isoformat() == "2026-09-01"
    assert registro["presenca"] == "compareceu"
    assert registro["disposicao"] == "boa"
    assert registro["feedback"] == "Foi muito bem hoje."
    assert len(registros) == 1
    assert registros[0]["id"] == registro["id"]


def test_list_sessoes_realizadas_orders_by_data_descending(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        older = create_sessao_realizada(
            aluno["id"], data="2026-01-10", presenca="compareceu"
        )
        newer = create_sessao_realizada(
            aluno["id"], data="2026-03-01", presenca="faltou"
        )

        registros = list_sessoes_realizadas(aluno["id"])

    assert [r["id"] for r in registros] == [newer["id"], older["id"]]


# --- routes --------------------------------------------------------------


def test_empty_registros_shows_empty_state(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/acompanhamento")

    assert response.status_code == 200
    assert "Ainda não há sessões registradas" in response.text


def test_unknown_aluno_id_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/9999/acompanhamento")

    assert response.status_code == 404
    assert "Aluno não encontrado." in response.text


def test_new_registro_form_shows_presenca_and_disposicao_fields(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/acompanhamento/novo")

    assert response.status_code == 200
    assert 'name="presenca"' in response.text
    assert 'name="disposicao"' in response.text


def test_post_valid_creates_registro_and_redirects_to_list(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/acompanhamento",
            data={
                "data": "2026-09-01",
                "presenca": "compareceu",
                "disposicao": "boa",
                "feedback": "Foi muito bem hoje.",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert (
            response.headers["location"] == f"/alunos/{aluno['id']}/acompanhamento"
        )

        followed = client.get(response.headers["location"])

    assert followed.status_code == 200
    assert "Compareceu" in followed.text
    assert "Foi muito bem hoje." in followed.text


def test_post_without_presenca_returns_400_and_preserves_values(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.post(
            f"/alunos/{aluno['id']}/acompanhamento",
            data={
                "data": "2026-09-01",
                "disposicao": "boa",
                "feedback": "Foi muito bem hoje.",
            },
        )

    assert response.status_code == 400
    assert "Presença inválida." in response.text
    assert 'value="2026-09-01"' in response.text
    assert (
        '<option value="boa" selected>Boa</option>' in response.text
    ), "the submitted disposicao (boa) should stay selected in the re-rendered form"
    assert "Foi muito bem hoje." in response.text


def test_remover_registro_removes_it_from_list_and_redirects(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        registro = create_sessao_realizada(
            aluno["id"], data="2026-09-01", presenca="compareceu"
        )

        response = client.post(
            f"/alunos/{aluno['id']}/acompanhamento/{registro['id']}/remover",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert (
            response.headers["location"] == f"/alunos/{aluno['id']}/acompanhamento"
        )

        registros = list_sessoes_realizadas(aluno["id"])

    assert registros == []


def test_remover_registro_of_another_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno1 = create_aluno(name="Maria Silva")
        aluno2 = create_aluno(name="João Souza")
        registro_de_aluno2 = create_sessao_realizada(
            aluno2["id"], data="2026-09-01", presenca="compareceu"
        )

        response = client.post(
            f"/alunos/{aluno1['id']}/acompanhamento/{registro_de_aluno2['id']}/remover"
        )

        assert response.status_code == 404
        assert "Aluno não encontrado." in response.text
        # The other student's registro must survive untouched.
        assert len(list_sessoes_realizadas(aluno2["id"])) == 1


def test_acompanhamento_subtab_present_and_has_no_coming_soon_marker(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/acompanhamento")

    assert response.status_code == 200

    active_link = (
        f'<a class="on" href="/alunos/{aluno["id"]}/acompanhamento">'
        "Acompanhamento</a>"
    )
    assert active_link in response.text

    nav_match = re.search(r"<nav[^>]*subnav[^>]*>(.*?)</nav>", response.text, re.DOTALL)
    assert nav_match is not None, "the ficha page should have a subnav"
    nav_html = nav_match.group(1)

    tab_link = re.search(
        rf'<a[^>]*href="/alunos/{aluno["id"]}/acompanhamento"[^>]*>(.*?)</a>',
        nav_html,
        re.DOTALL,
    )
    assert tab_link is not None
    assert "em breve" not in tab_link.group(1)
