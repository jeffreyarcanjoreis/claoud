"""Tests for issue 18 (Painel do mês): the consolidated monthly financial
overview, both the service function and the /financeiro route that renders
it.

Covers the functional specification:
- ``panorama_mes(ano, mes)`` combines: recebido, despesas, resultado
  (recebido - despesas), a_receber, mrr, ticket_medio, alunos_com_plano and
  sustentam (the active students who already paid this competence, with
  their paid value);
- when expenses exceed receipts, resultado is negative;
- with no data at all, recebido/despesas/resultado are zero and sustentam is
  empty;
- GET /financeiro renders the panel's labels ("Resultado do mês", "Quem
  sustenta o mês" and the two chart titles "Entradas × Saídas" /
  "Projeção"), the name of a student who paid this month, and the "nobody
  paid" empty state when nobody has.

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
    panorama_mes,
    registrar_despesa,
    registrar_pagamento,
    set_plano,
)
from kairos.main import app

hoje = datetime.date.today()


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_panorama_mes_combines_recebido_despesas_resultado_a_receber_mrr_e_sustentam(
    data_dir: Path,
) -> None:
    with TestClient(app):
        pago = create_aluno(name="Ana Paga", status="active")
        pendente = create_aluno(name="Beto Pendente", status="active")
        set_plano(pago["id"], formato="individual", valor="100")
        set_plano(pendente["id"], formato="individual", valor="200")
        registrar_pagamento(pago["id"], ano=hoje.year, mes=hoje.month, valor="100")
        registrar_despesa(data=hoje.isoformat(), descricao="Aluguel", valor="50")

        p = panorama_mes(hoje.year, hoje.month)

    assert p["recebido"] == Decimal("100.00")
    assert p["despesas"] == Decimal("50.00")
    assert p["resultado"] == Decimal("50.00")
    assert p["a_receber"] == Decimal("200.00")
    assert p["mrr"] == Decimal("300.00")
    assert p["alunos_com_plano"] == 2

    assert len(p["sustentam"]) == 1
    assert p["sustentam"][0]["aluno_nome"] == "Ana Paga"
    assert p["sustentam"][0]["valor_pago"] == Decimal("100.00")


def test_panorama_mes_resultado_negativo_quando_despesas_superam_recebido(
    data_dir: Path,
) -> None:
    with TestClient(app):
        registrar_despesa(data=hoje.isoformat(), descricao="Equipamento", valor="300")

        p = panorama_mes(hoje.year, hoje.month)

    assert p["recebido"] == Decimal("0.00")
    assert p["despesas"] == Decimal("300.00")
    assert p["resultado"] == Decimal("-300.00")
    assert p["resultado"] < 0


def test_panorama_mes_sem_dados_fica_tudo_zerado_e_sustentam_vazio(
    data_dir: Path,
) -> None:
    with TestClient(app):
        p = panorama_mes(hoje.year, hoje.month)

    assert p["recebido"] == Decimal("0.00")
    assert p["despesas"] == Decimal("0.00")
    assert p["resultado"] == Decimal("0.00")
    assert p["sustentam"] == []


def test_get_financeiro_shows_panel_labels(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/financeiro")

    assert response.status_code == 200
    text = response.text
    assert "Resultado do mês" in text
    assert "Entradas × Saídas" in text
    assert "Projeção" in text
    assert "Quem sustenta o mês" in text


def test_get_financeiro_shows_student_name_who_paid_this_month(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Carla Sustenta", status="active")
        set_plano(aluno["id"], formato="individual", valor="100")
        registrar_pagamento(aluno["id"], ano=hoje.year, mes=hoje.month, valor="100")

        response = client.get("/financeiro")

    assert response.status_code == 200
    assert "Carla Sustenta" in response.text


def test_get_financeiro_shows_empty_state_when_nobody_paid(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/financeiro")

    assert response.status_code == 200
    assert "Ninguém pagou ainda neste mês." in response.text
