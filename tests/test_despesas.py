"""Tests for issue 17 (financeiro: despesas / saidas).

Covers the functional specification:

Service layer (kairos.financeiro.service):
- registrar_despesa without a data raises ValidationError;
- registrar_despesa without a descricao raises ValidationError;
- registrar_despesa without a valor raises ValidationError;
- registrar_despesa with valor "0" raises ValidationError (must be strictly
  positive);
- registrar_despesa with an invalid categoria ("xpto") raises
  ValidationError;
- registrar_despesa with an empty categoria ("") persists categoria as None
  (rule 6: empty optional means NULL, not a fake default);
- a valid registrar_despesa (accepting comma as the decimal separator)
  persists and get_despesa reads it back;
- remover_despesa removes an expense;
- despesas_do_mes(ano, mes) returns only the expenses of the given month,
  most recent date first, and an expense from a different month never shows
  up;
- total_despesas_mes(ano, mes) sums the values of the expenses of the given
  month.

Routes / panel:
- GET /financeiro/despesas with no expenses returns 200, shows "Total do
  mes" and the empty state "Nenhuma despesa neste mes.";
- POST /financeiro/despesas with valid data redirects (303) to
  /financeiro/despesas; the next GET shows the description and the
  formatted value;
- POST /financeiro/despesas without a descricao returns 400 with an error
  message and preserves the typed values;
- POST /financeiro/despesas/{despesa_id}/remover redirects (303) and the
  expense is gone;
- GET /financeiro (panel) has a link to /financeiro/despesas.

Same isolation pattern as tests/test_agenda_global.py: KAIROS_DATA_DIR points
at a temp dir and the cached engine is disposed on teardown.
"""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.financeiro.service import (
    ValidationError,
    despesas_do_mes,
    get_despesa,
    registrar_despesa,
    remover_despesa,
    total_despesas_mes,
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


hoje = datetime.date.today()


# ---------------------------------------------------------------------------
# Service layer: registrar_despesa validation
# ---------------------------------------------------------------------------


def test_registrar_despesa_without_data_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            registrar_despesa(descricao="Software", valor="49,90")


def test_registrar_despesa_without_descricao_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            registrar_despesa(data=hoje.isoformat(), valor="49,90")


def test_registrar_despesa_without_valor_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            registrar_despesa(data=hoje.isoformat(), descricao="Software")


def test_registrar_despesa_with_zero_valor_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            registrar_despesa(
                data=hoje.isoformat(), descricao="Software", valor="0"
            )


def test_registrar_despesa_with_invalid_categoria_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        with pytest.raises(ValidationError):
            registrar_despesa(
                data=hoje.isoformat(),
                descricao="Software",
                categoria="xpto",
                valor="49,90",
            )


def test_registrar_despesa_with_empty_categoria_persists_as_none(
    data_dir: Path,
) -> None:
    with TestClient(app):
        registrada = registrar_despesa(
            data=hoje.isoformat(),
            descricao="Software",
            categoria="",
            valor="49,90",
        )

    assert registrada["categoria"] is None


def test_registrar_despesa_valid_accepts_comma_decimal_and_is_read_back(
    data_dir: Path,
) -> None:
    with TestClient(app):
        registrada = registrar_despesa(
            data=hoje.isoformat(),
            descricao="Software",
            categoria="software",
            valor="49,90",
        )

        assert registrada["data"] == hoje
        assert registrada["descricao"] == "Software"
        assert registrada["categoria"] == "software"
        assert registrada["valor"] == Decimal("49.90")

        lida = get_despesa(registrada["id"])

    assert lida is not None
    assert lida["data"] == hoje
    assert lida["descricao"] == "Software"
    assert lida["categoria"] == "software"
    assert lida["valor"] == Decimal("49.90")


def test_remover_despesa_removes_it(data_dir: Path) -> None:
    with TestClient(app):
        registrada = registrar_despesa(
            data=hoje.isoformat(), descricao="Software", valor="49,90"
        )

        removida = remover_despesa(registrada["id"])

        assert removida is True
        assert get_despesa(registrada["id"]) is None


def test_remover_despesa_returns_false_when_there_was_none(data_dir: Path) -> None:
    with TestClient(app):
        assert remover_despesa(9999) is False


# ---------------------------------------------------------------------------
# Service layer: despesas_do_mes / total_despesas_mes
# ---------------------------------------------------------------------------


def test_despesas_do_mes_orders_by_data_desc_and_excludes_other_months(
    data_dir: Path,
) -> None:
    with TestClient(app):
        registrar_despesa(
            data=datetime.date(hoje.year, hoje.month, 1).isoformat(),
            descricao="Antiga",
            valor="10",
        )
        registrar_despesa(
            data=datetime.date(hoje.year, hoje.month, 2).isoformat(),
            descricao="Recente",
            valor="20",
        )
        outro_mes = datetime.date(hoje.year - 1, hoje.month, 5)
        registrar_despesa(
            data=outro_mes.isoformat(), descricao="Outro mes", valor="30"
        )

        despesas = despesas_do_mes(hoje.year, hoje.month)

    descricoes = [d["descricao"] for d in despesas]
    assert "Outro mes" not in descricoes
    assert descricoes.index("Recente") < descricoes.index("Antiga")


def test_total_despesas_mes_sums_only_current_month(data_dir: Path) -> None:
    with TestClient(app):
        registrar_despesa(data=hoje.isoformat(), descricao="Uma", valor="100")
        registrar_despesa(data=hoje.isoformat(), descricao="Duas", valor="50")
        outro_mes = datetime.date(hoje.year - 1, hoje.month, 5)
        registrar_despesa(
            data=outro_mes.isoformat(), descricao="Outro mes", valor="999"
        )

        total = total_despesas_mes(hoje.year, hoje.month)

    assert total == Decimal("150.00")


def test_total_despesas_mes_is_zero_when_there_are_no_expenses(
    data_dir: Path,
) -> None:
    with TestClient(app):
        total = total_despesas_mes(hoje.year, hoje.month)

    assert total == Decimal("0.00")


# ---------------------------------------------------------------------------
# Routes / panel
# ---------------------------------------------------------------------------


def test_get_despesas_with_no_expenses_shows_total_and_empty_state(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.get("/financeiro/despesas")

    assert response.status_code == 200
    text = response.text
    assert "Total do mês" in text
    assert "Nenhuma despesa neste mês." in text
    assert "R$ 0,00" in text


def test_post_despesas_valid_redirects_and_next_get_shows_it(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/financeiro/despesas",
            data={
                "data": hoje.isoformat(),
                "descricao": "Aluguel",
                "valor": "800",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/financeiro/despesas"

        confirmacao = client.get("/financeiro/despesas")

    assert confirmacao.status_code == 200
    assert "Aluguel" in confirmacao.text
    assert "R$ 800,00" in confirmacao.text


def test_post_despesas_without_descricao_returns_400_and_preserves_values(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/financeiro/despesas",
            data={"data": hoje.isoformat(), "valor": "800"},
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Descrição é obrigatória." in response.text
    assert f'value="{hoje.isoformat()}"' in response.text
    assert 'value="800"' in response.text


def test_post_despesas_remover_redirects_and_it_is_gone(data_dir: Path) -> None:
    with TestClient(app) as client:
        registrada = registrar_despesa(
            data=hoje.isoformat(), descricao="Aluguel", valor="800"
        )

        response = client.post(
            f"/financeiro/despesas/{registrada['id']}/remover",
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/financeiro/despesas"

        confirmacao = client.get("/financeiro/despesas")

    assert get_despesa(registrada["id"]) is None
    # "Aluguel" still appears as a <select> category option, so check the
    # empty-state message instead of the mere absence of the word.
    assert "Nenhuma despesa neste mês." in confirmacao.text


def test_financeiro_panel_links_to_despesas(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/financeiro")

    assert response.status_code == 200
    assert 'href="/financeiro/despesas"' in response.text
