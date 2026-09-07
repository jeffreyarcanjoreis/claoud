"""Tests for issue 19 (Financeiro -- gráficos): the service-layer series.

Covers the functional specification for `kairos.financeiro.service`:
- `serie_entradas_saidas(meses=6)` returns the last `meses` months (oldest
  first), the last one being the current month; each item sums Pagamento
  (recebido) and Despesa (despesas) values for that competence/date range.
- `projecao_receita(meses=6)` returns the next `meses` months (nearest
  first), the first one being the current month; for each month, sums the
  value and counts the ACTIVE students whose plan is still within its
  contract window -- a plan without `inicio`/`ciclo_meses` is assumed to
  keep recurring indefinitely, one with both fields only counts while
  `mes < inicio + ciclo`. Inactive students never count, even with a plan.

Same isolation pattern as tests/test_agenda_global.py: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on teardown.
"""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.financeiro.service import (
    projecao_receita,
    registrar_despesa,
    registrar_pagamento,
    serie_entradas_saidas,
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
# serie_entradas_saidas
# ---------------------------------------------------------------------------


def test_serie_entradas_saidas_has_six_months_last_is_current(
    data_dir: Path,
) -> None:
    hoje = datetime.date.today()

    with TestClient(app):
        serie = serie_entradas_saidas(6)

    assert len(serie) == 6
    assert serie[-1]["ano"] == hoje.year
    assert serie[-1]["mes"] == hoje.month


def test_serie_entradas_saidas_current_month_sums_pagamento_and_despesa(
    data_dir: Path,
) -> None:
    hoje = datetime.date.today()

    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")
        registrar_pagamento(
            aluno["id"], ano=hoje.year, mes=hoje.month, valor="100"
        )
        registrar_despesa(
            data=hoje.isoformat(), descricao="Aluguel", valor="50"
        )

        serie = serie_entradas_saidas(6)

    assert serie[-1]["recebido"] == Decimal("100.00")
    assert serie[-1]["despesas"] == Decimal("50.00")

    for item in serie[:-1]:
        assert item["recebido"] == Decimal("0")
        assert item["despesas"] == Decimal("0")


# ---------------------------------------------------------------------------
# projecao_receita
# ---------------------------------------------------------------------------


def test_projecao_receita_has_six_months_first_is_current(
    data_dir: Path,
) -> None:
    hoje = datetime.date.today()

    with TestClient(app):
        projecao = projecao_receita(6)

    assert len(projecao) == 6
    assert projecao[0]["ano"] == hoje.year
    assert projecao[0]["mes"] == hoje.month


def test_projecao_receita_active_plan_without_ciclo_counts_every_month(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")
        set_plano(aluno["id"], formato="individual", valor="200")

        projecao = projecao_receita(6)

    assert len(projecao) == 6
    for item in projecao:
        assert item["receita"] == Decimal("200.00")
        assert item["alunos"] == 1


def test_projecao_receita_plan_with_inicio_e_ciclo_decays_after_contract(
    data_dir: Path,
) -> None:
    hoje = datetime.date.today()

    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="active")
        set_plano(
            aluno["id"],
            formato="individual",
            valor="200",
            inicio=hoje.isoformat(),
            ciclo_meses="3",
        )

        projecao = projecao_receita(6)

    assert len(projecao) == 6
    for item in projecao[:3]:
        assert item["receita"] == Decimal("200.00")
        assert item["alunos"] == 1
    for item in projecao[3:]:
        assert item["receita"] == Decimal("0")
        assert item["alunos"] == 0


def test_projecao_receita_ignores_inactive_student_with_plan(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Ana Lima", status="inactive")
        set_plano(aluno["id"], formato="individual", valor="200")

        projecao = projecao_receita(6)

    assert len(projecao) == 6
    for item in projecao:
        assert item["receita"] == Decimal("0")
        assert item["alunos"] == 0
