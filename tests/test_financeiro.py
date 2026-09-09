"""Tests for issue 15: Financeiro -- plano & valor do aluno.

Covers the functional specification:
- service layer (`kairos.financeiro.service`): `set_plano` requires a valid
  `formato` (digital/grupo/individual) and a strictly positive `valor`
  (accepting comma or dot as the decimal separator); `ciclo_meses`, `inicio`
  and `observacao` are optional and normalize to None when blank; invalid
  input raises `ValidationError` and nothing is persisted; a student has at
  most one plan (`set_plano` upserts: calling it again for the same student
  updates the existing plan instead of creating a second one); `get_plano`
  returns the plan dict or None; `remover_plano` removes the plan and
  reports whether one existed;
- `resumo_financeiro()` aggregates over ACTIVE students with a plan only:
  `mrr` is the sum of their monthly values, `alunos_com_plano` is their
  count, `ticket_medio` is `mrr` divided by that count (or None when there
  are no such students -- never a fabricated zero);
- routes: `GET /alunos/{id}/financeiro` renders the sub-tab (plan or "sem
  plano" state) or 404 for an unknown student; `POST
  /alunos/{id}/financeiro` validates and upserts the plan (400 + preserved
  values on error, 303 redirect on success) or 404 for an unknown student;
  `POST /alunos/{id}/financeiro/remover` removes the plan and redirects,
  or 404 for an unknown student;
- the ficha's "Financeiro" sub-tab no longer carries an "em breve" marker;
- `GET /financeiro` (panel) shows the real indicators instead of the old
  "em breve" placeholder;
- the Início page's "Financeiro" tile shows a real "R$ ..." value instead
  of "em breve".

Same isolation pattern as tests/test_agenda_global.py: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on teardown.
"""

import re
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.financeiro.service import (
    ValidationError,
    get_plano,
    remover_plano,
    resumo_financeiro,
    set_plano,
)
from kairos.main import app


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# Service layer: validation
# ---------------------------------------------------------------------------


def test_set_plano_without_formato_raises_validation_error(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        with pytest.raises(ValidationError):
            set_plano(aluno["id"], formato=None, valor="100")


def test_set_plano_with_invalid_formato_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        with pytest.raises(ValidationError):
            set_plano(aluno["id"], formato="x", valor="100")


def test_set_plano_without_valor_raises_validation_error(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        with pytest.raises(ValidationError):
            set_plano(aluno["id"], formato="digital", valor=None)


def test_set_plano_with_zero_valor_raises_validation_error(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        with pytest.raises(ValidationError):
            set_plano(aluno["id"], formato="digital", valor="0")


def test_set_plano_with_non_numeric_valor_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        with pytest.raises(ValidationError):
            set_plano(aluno["id"], formato="digital", valor="abc")


def test_invalid_set_plano_does_not_persist_anything(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        with pytest.raises(ValidationError):
            set_plano(aluno["id"], formato="digital", valor="0")

        assert get_plano(aluno["id"]) is None


# ---------------------------------------------------------------------------
# Service layer: create, upsert, read, remove
# ---------------------------------------------------------------------------


def test_set_plano_valid_accepts_comma_decimal_and_optional_fields(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        plano = set_plano(
            aluno["id"],
            formato="individual",
            valor="150,00",
            ciclo_meses="6",
            inicio="2026-09-01",
        )

    assert plano["formato"] == "individual"
    assert plano["valor"] == Decimal("150.00")
    assert plano["ciclo_meses"] == 6
    assert plano["inicio"].isoformat() == "2026-09-01"


def test_set_plano_called_twice_upserts_a_single_plan(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        first = set_plano(aluno["id"], formato="digital", valor="100")
        second = set_plano(aluno["id"], formato="grupo", valor="80")

        plano = get_plano(aluno["id"])

    assert first["id"] == second["id"]  # same row, updated in place
    assert plano is not None
    assert plano["formato"] == "grupo"
    assert plano["valor"] == Decimal("80.00")


def test_get_plano_returns_none_when_student_has_no_plan(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        assert get_plano(aluno["id"]) is None


def test_get_plano_returns_the_saved_plan(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")
        set_plano(aluno["id"], formato="digital", valor="120")

        plano = get_plano(aluno["id"])

    assert plano is not None
    assert plano["formato"] == "digital"
    assert plano["valor"] == Decimal("120.00")


def test_remover_plano_removes_existing_plan_and_returns_true(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")
        set_plano(aluno["id"], formato="digital", valor="120")

        removed = remover_plano(aluno["id"])

    assert removed is True
    assert get_plano(aluno["id"]) is None


def test_remover_plano_returns_false_when_there_was_no_plan(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")

        removed = remover_plano(aluno["id"])

    assert removed is False


# ---------------------------------------------------------------------------
# Service layer: resumo_financeiro (indicators)
# ---------------------------------------------------------------------------


def test_resumo_financeiro_counts_only_active_students_with_plan(
    data_dir: Path,
) -> None:
    with TestClient(app):
        ativo_a = create_aluno(name="Ativo Um", status="active")
        ativo_b = create_aluno(name="Ativo Dois", status="active")
        inativo = create_aluno(name="Inativo", status="inactive")

        set_plano(ativo_a["id"], formato="digital", valor="100")
        set_plano(ativo_b["id"], formato="grupo", valor="200")
        set_plano(inativo["id"], formato="individual", valor="999")

        resumo = resumo_financeiro()

    assert resumo["mrr"] == Decimal("300.00")
    assert resumo["alunos_com_plano"] == 2
    assert resumo["ticket_medio"] == Decimal("150.00")


def test_resumo_financeiro_with_no_plans_returns_zero_mrr_and_no_ticket(
    data_dir: Path,
) -> None:
    with TestClient(app):
        create_aluno(name="Sem Plano", status="active")

        resumo = resumo_financeiro()

    assert resumo["mrr"] == Decimal("0")
    assert resumo["alunos_com_plano"] == 0
    assert resumo["ticket_medio"] is None


# ---------------------------------------------------------------------------
# Routes: student's "Financeiro" sub-tab
# ---------------------------------------------------------------------------


def test_get_financeiro_subtab_unknown_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/9999/financeiro")

    assert response.status_code == 404


def test_get_financeiro_subtab_without_plan_shows_sem_plano(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Lima", status="active")

        response = client.get(f"/alunos/{aluno['id']}/financeiro")

    assert response.status_code == 200
    assert "Ainda sem plano" in response.text


def test_post_financeiro_valid_redirects_to_subtab(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Lima", status="active")

        response = client.post(
            f"/alunos/{aluno['id']}/financeiro",
            data={"formato": "individual", "valor": "150,00"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == f"/alunos/{aluno['id']}/financeiro"


def test_post_financeiro_valid_then_get_shows_formatted_value_and_formato(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Lima", status="active")

        client.post(
            f"/alunos/{aluno['id']}/financeiro",
            data={"formato": "individual", "valor": "150,00"},
            follow_redirects=False,
        )

        response = client.get(f"/alunos/{aluno['id']}/financeiro")

    assert response.status_code == 200
    assert "R$ 150,00" in response.text
    assert "Individual" in response.text


def test_post_financeiro_without_valor_returns_400_with_error_and_preserves_values(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Lima", status="active")

        response = client.post(
            f"/alunos/{aluno['id']}/financeiro",
            data={"formato": "individual", "ciclo_meses": "3"},
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Valor é obrigatório." in response.text
    # Values already typed by the coach are preserved on the re-rendered form.
    assert 'value="individual" selected' in response.text
    assert 'value="3"' in response.text
    # The failed attempt must not have been persisted.
    assert get_plano(aluno["id"]) is None


def test_post_financeiro_unknown_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos/9999/financeiro",
            data={"formato": "individual", "valor": "150"},
            follow_redirects=False,
        )

    assert response.status_code == 404


def test_post_financeiro_remover_redirects_and_plan_is_gone(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Lima", status="active")
        set_plano(aluno["id"], formato="digital", valor="100")

        response = client.post(
            f"/alunos/{aluno['id']}/financeiro/remover", follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"] == f"/alunos/{aluno['id']}/financeiro"

        follow_up = client.get(f"/alunos/{aluno['id']}/financeiro")

    assert get_plano(aluno["id"]) is None
    assert follow_up.status_code == 200
    assert "Ainda sem plano" in follow_up.text


def test_post_financeiro_remover_unknown_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/alunos/9999/financeiro/remover", follow_redirects=False
        )

    assert response.status_code == 404


def test_financeiro_subtab_link_has_no_em_breve_marker(data_dir: Path) -> None:
    """The sub-tab's own nav link no longer carries the "em breve" wording
    it had before issue 15 (unlike the still-placeholder sub-tabs)."""
    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Lima", status="active")

        response = client.get(f"/alunos/{aluno['id']}/financeiro")

    assert response.status_code == 200
    subnav_match = re.search(
        r'<nav class="subnav">(.*?)</nav>', response.text, re.DOTALL
    )
    assert subnav_match is not None
    financeiro_link_match = re.search(
        r'<a[^>]*href="/alunos/\d+/financeiro"[^>]*>(.*?)</a>',
        subnav_match.group(1),
        re.DOTALL,
    )
    assert financeiro_link_match is not None
    assert "em breve" not in financeiro_link_match.group(1)


# ---------------------------------------------------------------------------
# Painel: GET /financeiro
# ---------------------------------------------------------------------------


def test_painel_financeiro_shows_real_indicators(data_dir: Path) -> None:
    with TestClient(app) as client:
        ativo = create_aluno(name="Ativo Um", status="active")
        set_plano(ativo["id"], formato="digital", valor="100")

        response = client.get("/financeiro")

    assert response.status_code == 200
    assert "Resultado do mês" in response.text
    assert "Projeção" in response.text
    assert "serie-projecao" in response.text
    assert "R$" in response.text


def test_painel_financeiro_shows_zero_and_sem_registro_when_no_plans(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/financeiro")

    assert response.status_code == 200
    assert "R$ 0,00" in response.text
    assert "Sem planos ativos para projetar" in response.text


# ---------------------------------------------------------------------------
# Início tile
# ---------------------------------------------------------------------------


def test_inicio_financeiro_tile_shows_mrr_value_not_em_breve(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        ativo = create_aluno(name="Ativo Um", status="active")
        set_plano(ativo["id"], formato="digital", valor="1200")

        response = client.get("/")

    assert response.status_code == 200
    tile_match = re.search(
        r'<a class="stat" href="/financeiro">\s*<div class="n">(.*?)</div>\s*'
        r'<div class="l">Financeiro</div>',
        response.text,
        re.DOTALL,
    )
    assert tile_match is not None, "the Início page should have the Financeiro tile"
    assert "R$ 1.200,00" in tile_match.group(1)


def test_inicio_financeiro_tile_shows_zero_when_no_plans(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    tile_match = re.search(
        r'<a class="stat" href="/financeiro">\s*<div class="n">(.*?)</div>\s*'
        r'<div class="l">Financeiro</div>',
        response.text,
        re.DOTALL,
    )
    assert tile_match is not None
    assert "R$ 0,00" in tile_match.group(1)
