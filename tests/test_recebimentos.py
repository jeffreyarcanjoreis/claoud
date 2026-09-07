"""Tests for issue 16 (financeiro: recebimentos / mensalidades).

Covers the functional specification:

Service layer (kairos.financeiro.service):
- registrar_pagamento without a valor raises ValidationError;
- registrar_pagamento with valor "0" raises ValidationError (must be
  strictly positive);
- registrar_pagamento with valor "abc" raises ValidationError (must be a
  valid number);
- a valid registrar_pagamento (valor="100", no data_pagamento) persists and
  defaults the payment date to today; get_pagamento reads it back;
- registrar_pagamento is an upsert: calling it again for the same
  (aluno_id, ano, mes) updates the existing row in place (no duplicate),
  and the value changes;
- remover_pagamento removes a payment;
- pagamentos_do_aluno orders payments by competence, most recent first.

recebimentos_do_mes / resumo_recebimentos_mes:
- with 2 active students with a plan (values 100 and 200), 1 active student
  with no plan, and 1 inactive student with a plan, and a payment
  registered for the current month for ONE of the active-with-plan
  students (value 100): recebimentos_do_mes(ano, mes) of the current month
  has exactly 2 rows (the two active-with-plan students only -- the
  no-plan and the inactive students never show up), one paid and one not;
  resumo_recebimentos_mes gives recebido == 100.00, pendente == 200.00,
  total_esperado == 300.00.

Routes / panel:
- GET /financeiro/recebimentos returns 200, shows "Recebido"/"Pendente" and
  the names of the active-with-plan students;
- POST /financeiro/recebimentos registers a payment and redirects (303) to
  /financeiro/recebimentos; the next GET shows that student as paid;
- POST /financeiro/recebimentos without a valor returns 400 with an error
  message;
- POST /financeiro/recebimentos/{pagamento_id}/remover redirects (303);
- GET /financeiro has a link to /financeiro/recebimentos;
- GET /alunos/{id}/financeiro of a student with a payment shows the
  competence ("%02d/%d" of month/year) in the "Recebimentos" section.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.financeiro.service import (
    ValidationError,
    get_pagamento,
    pagamentos_do_aluno,
    recebimentos_do_mes,
    registrar_pagamento,
    remover_pagamento,
    resumo_recebimentos_mes,
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


hoje = datetime.date.today()


# --- service layer: registrar_pagamento validation and upsert -------------


def test_registrar_pagamento_without_valor_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            registrar_pagamento(aluno["id"], ano=hoje.year, mes=hoje.month)


def test_registrar_pagamento_with_zero_valor_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            registrar_pagamento(
                aluno["id"], ano=hoje.year, mes=hoje.month, valor="0"
            )


def test_registrar_pagamento_with_non_numeric_valor_raises_validation_error(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        with pytest.raises(ValidationError):
            registrar_pagamento(
                aluno["id"], ano=hoje.year, mes=hoje.month, valor="abc"
            )


def test_registrar_pagamento_valid_without_data_defaults_to_today(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        registrado = registrar_pagamento(
            aluno["id"], ano=hoje.year, mes=hoje.month, valor="100"
        )

        assert registrado["valor"] == Decimal("100.00")
        assert registrado["data_pagamento"] == hoje

        lido = get_pagamento(registrado["id"])
        assert lido is not None
        assert lido["aluno_id"] == aluno["id"]
        assert lido["ano"] == hoje.year
        assert lido["mes"] == hoje.month
        assert lido["valor"] == Decimal("100.00")
        assert lido["data_pagamento"] == hoje


def test_registrar_pagamento_twice_same_competencia_upserts_instead_of_duplicating(
    data_dir: Path,
) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        primeiro = registrar_pagamento(
            aluno["id"], ano=hoje.year, mes=hoje.month, valor="100"
        )
        segundo = registrar_pagamento(
            aluno["id"], ano=hoje.year, mes=hoje.month, valor="150"
        )

        assert segundo["id"] == primeiro["id"]
        assert segundo["valor"] == Decimal("150.00")

        todos = pagamentos_do_aluno(aluno["id"])
        assert len(todos) == 1
        assert todos[0]["valor"] == Decimal("150.00")


def test_remover_pagamento_removes_it(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        registrado = registrar_pagamento(
            aluno["id"], ano=hoje.year, mes=hoje.month, valor="100"
        )

        removido = remover_pagamento(registrado["id"])

        assert removido is True
        assert get_pagamento(registrado["id"]) is None


def test_pagamentos_do_aluno_orders_by_competencia_desc(data_dir: Path) -> None:
    with TestClient(app):
        aluno = create_aluno(name="Maria Silva")

        registrar_pagamento(aluno["id"], ano=2025, mes=6, valor="100")
        registrar_pagamento(aluno["id"], ano=2026, mes=1, valor="100")
        registrar_pagamento(aluno["id"], ano=2025, mes=12, valor="100")

        pagamentos = pagamentos_do_aluno(aluno["id"])

        competencias = [(p["ano"], p["mes"]) for p in pagamentos]
        assert competencias == [(2026, 1), (2025, 12), (2025, 6)]


# --- recebimentos_do_mes / resumo_recebimentos_mes -------------------------


def _preparar_cenario() -> dict:
    """Create the students described in the spec and return their ids."""
    ativo_pago = create_aluno(name="Ana Ativa Paga", status="active")
    set_plano(ativo_pago["id"], formato="individual", valor="100")

    ativo_pendente = create_aluno(name="Bruno Ativo Pendente", status="active")
    set_plano(ativo_pendente["id"], formato="individual", valor="200")

    ativo_sem_plano = create_aluno(name="Carla Sem Plano", status="active")

    inativo_com_plano = create_aluno(name="Diego Inativo", status="inactive")
    set_plano(inativo_com_plano["id"], formato="individual", valor="300")

    registrar_pagamento(
        ativo_pago["id"], ano=hoje.year, mes=hoje.month, valor="100"
    )

    return {
        "ativo_pago": ativo_pago,
        "ativo_pendente": ativo_pendente,
        "ativo_sem_plano": ativo_sem_plano,
        "inativo_com_plano": inativo_com_plano,
    }


def test_recebimentos_do_mes_includes_only_active_students_with_plan(
    data_dir: Path,
) -> None:
    with TestClient(app):
        cenario = _preparar_cenario()

        linhas = recebimentos_do_mes(hoje.year, hoje.month)

    assert len(linhas) == 2

    nomes = {linha["aluno_id"] for linha in linhas}
    assert nomes == {
        cenario["ativo_pago"]["id"],
        cenario["ativo_pendente"]["id"],
    }

    por_aluno = {linha["aluno_id"]: linha for linha in linhas}
    assert por_aluno[cenario["ativo_pago"]["id"]]["pago"] is True
    assert por_aluno[cenario["ativo_pendente"]["id"]]["pago"] is False


def test_resumo_recebimentos_mes_computes_recebido_pendente_total(
    data_dir: Path,
) -> None:
    with TestClient(app):
        _preparar_cenario()

        resumo = resumo_recebimentos_mes(hoje.year, hoje.month)

    assert resumo["recebido"] == Decimal("100.00")
    assert resumo["pendente"] == Decimal("200.00")
    assert resumo["total_esperado"] == Decimal("300.00")


# --- routes / panel ---------------------------------------------------------


def test_get_recebimentos_shows_recebido_pendente_and_student_names(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        cenario = _preparar_cenario()

        response = client.get("/financeiro/recebimentos")

    assert response.status_code == 200
    text = response.text
    assert "Recebido" in text
    assert "Pendente" in text
    assert cenario["ativo_pago"]["name"] in text
    assert cenario["ativo_pendente"]["name"] in text


def test_post_recebimentos_registers_payment_and_redirects(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva", status="active")
        set_plano(aluno["id"], formato="individual", valor="100")

        response = client.post(
            "/financeiro/recebimentos",
            data={
                "aluno_id": str(aluno["id"]),
                "valor": "100",
                "data_pagamento": hoje.isoformat(),
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/financeiro/recebimentos"

        confirmacao = client.get("/financeiro/recebimentos")

    text = confirmacao.text
    assert "Pago" in text or "Desfazer" in text
    assert aluno["name"] in text


def test_post_recebimentos_without_valor_returns_400_with_error(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva", status="active")
        set_plano(aluno["id"], formato="individual", valor="100")

        response = client.post(
            "/financeiro/recebimentos",
            data={"aluno_id": str(aluno["id"])},
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Valor" in response.text


def test_post_recebimentos_remover_redirects(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva", status="active")
        set_plano(aluno["id"], formato="individual", valor="100")
        registrado = registrar_pagamento(
            aluno["id"], ano=hoje.year, mes=hoje.month, valor="100"
        )

        response = client.post(
            f"/financeiro/recebimentos/{registrado['id']}/remover",
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/financeiro/recebimentos"


def test_financeiro_panel_links_to_recebimentos(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/financeiro")

    assert response.status_code == 200
    assert 'href="/financeiro/recebimentos"' in response.text


def test_aluno_financeiro_shows_competencia_of_payment(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva", status="active")
        registrar_pagamento(
            aluno["id"], ano=hoje.year, mes=hoje.month, valor="100"
        )

        response = client.get(f"/alunos/{aluno['id']}/financeiro")

    assert response.status_code == 200
    competencia_esperada = f"{hoje.month:02d}/{hoje.year}"
    assert competencia_esperada in response.text
