"""Tests for issue 19 (Financeiro -- gráficos): chart geometry helpers and
the `GET /financeiro` route that renders them.

Covers the functional specification for `kairos.financeiro.graficos`:
- `grafico_entradas_saidas(serie)` reports `empty` when the series is empty
  or every value is zero; otherwise it produces two bars per month (entrada
  and saida) and non-empty y-axis ticks.
- `grafico_projecao(serie)` reports `empty` under the same conditions;
  otherwise it produces one point per month and a non-empty SVG polyline.

And for `GET /financeiro`:
- with data (a payment and an expense in the current month), the page
  renders both `<svg>` charts, their titles ("Entradas × Saídas" and
  "Projeção") and at least one series class (`.serie-entrada`/`.serie-saida`).
- with no data at all, the page shows the honest empty-state messages
  instead of empty axes.

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
from kairos.financeiro.graficos import grafico_entradas_saidas, grafico_projecao
from kairos.financeiro.service import (
    registrar_despesa,
    registrar_pagamento,
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
# grafico_entradas_saidas
# ---------------------------------------------------------------------------


def test_grafico_entradas_saidas_empty_series_is_empty() -> None:
    grafico = grafico_entradas_saidas([])

    assert grafico["empty"] is True


def test_grafico_entradas_saidas_all_zero_values_is_empty() -> None:
    serie = [
        {"ano": 2026, "mes": 6, "recebido": Decimal("0"), "despesas": Decimal("0")},
        {"ano": 2026, "mes": 7, "recebido": Decimal("0"), "despesas": Decimal("0")},
    ]

    grafico = grafico_entradas_saidas(serie)

    assert grafico["empty"] is True


def test_grafico_entradas_saidas_two_months_produce_four_bars_and_ticks() -> None:
    serie = [
        {"ano": 2026, "mes": 6, "recebido": Decimal("100"), "despesas": Decimal("40")},
        {"ano": 2026, "mes": 7, "recebido": Decimal("150"), "despesas": Decimal("60")},
    ]

    grafico = grafico_entradas_saidas(serie)

    assert grafico["empty"] is False
    assert len(grafico["bars"]) == 4
    assert grafico["y_ticks"] != []
    for bar in grafico["bars"]:
        assert bar["serie"] in {"entrada", "saida"}


# ---------------------------------------------------------------------------
# grafico_projecao
# ---------------------------------------------------------------------------


def test_grafico_projecao_empty_series_is_empty() -> None:
    grafico = grafico_projecao([])

    assert grafico["empty"] is True


def test_grafico_projecao_all_zero_values_is_empty() -> None:
    serie = [
        {"ano": 2026, "mes": 6, "receita": Decimal("0"), "alunos": 0},
        {"ano": 2026, "mes": 7, "receita": Decimal("0"), "alunos": 0},
    ]

    grafico = grafico_projecao(serie)

    assert grafico["empty"] is True


def test_grafico_projecao_with_data_produces_points_and_polyline() -> None:
    serie = [
        {"ano": 2026, "mes": 6, "receita": Decimal("200"), "alunos": 1},
        {"ano": 2026, "mes": 7, "receita": Decimal("200"), "alunos": 1},
    ]

    grafico = grafico_projecao(serie)

    assert grafico["empty"] is False
    assert grafico["points"] != []
    assert grafico["polyline"] != ""


# ---------------------------------------------------------------------------
# GET /financeiro
# ---------------------------------------------------------------------------


def test_financeiro_page_with_data_renders_svg_charts_and_titles(
    data_dir: Path,
) -> None:
    hoje = datetime.date.today()

    with TestClient(app) as client:
        aluno = create_aluno(name="Ana Lima", status="active")
        set_plano(aluno["id"], formato="individual", valor="200")
        registrar_pagamento(
            aluno["id"], ano=hoje.year, mes=hoje.month, valor="200"
        )
        registrar_despesa(
            data=hoje.isoformat(), descricao="Aluguel", valor="50"
        )

        response = client.get("/financeiro")

    assert response.status_code == 200
    assert "<svg" in response.text
    assert "Entradas × Saídas" in response.text
    assert "Projeção" in response.text
    assert "serie-entrada" in response.text or "serie-saida" in response.text


def test_financeiro_page_without_data_shows_empty_state(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/financeiro")

    assert response.status_code == 200
    assert (
        "Ainda sem dados para o período" in response.text
        or "Sem planos ativos para projetar" in response.text
    )
