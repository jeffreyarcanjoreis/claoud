"""Tests for issue 25 (Parte B): the end-to-end functional flow, proving
every domain in the app genuinely connects, following the coach's real
journey: a lead arrives -> becomes a student -> enters the financeiro ->
gets an assessment, a workout and a scheduled session (which automatically
creates a follow-up task, issue 25 Parte A) -> a held session is logged.

Each step is asserted through the service layer (and, where the issue asks
for it, through the actual HTTP route via TestClient) so a break in any link
of the chain shows up as a test failure rather than a silent gap.

Same isolation pattern as the other route suites: KAIROS_DATA_DIR points at
a temp dir and the cached engine is disposed on setup/teardown. Migrations
run automatically through the FastAPI app's lifespan when TestClient is
used as a context manager, so every service call below happens inside that
``with`` block.
"""

import datetime
import re
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.acompanhamento.service import (
    create_sessao_realizada,
    list_sessoes_realizadas,
)
from kairos.agenda.service import create_sessao, list_sessoes
from kairos.alunos.service import get_aluno, list_alunos
from kairos.avaliacoes.service import create_avaliacao, list_avaliacoes
from kairos.contatos.service import list_contatos_abertos
from kairos.financeiro.service import (
    panorama_mes,
    registrar_pagamento,
    resumo_financeiro,
    set_plano,
)
from kairos.main import app
from kairos.tarefas.service import list_tarefas_abertas
from kairos.treinos.service import (
    add_item_to_treino,
    create_exercicio,
    create_treino,
    get_treino_detail,
    list_treinos,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_fluxo_lead_ate_acompanhamento(data_dir: Path) -> None:
    nome = "Fernanda Costa"
    contato_valor = "fernanda@example.com"
    idade = "34"
    sexo = "feminino"
    objetivo = "Emagrecimento e condicionamento"
    frequencia_desejada = "3-4"
    nivel_condicionamento = "iniciante"
    condicoes = "Hipertensão controlada"
    lesoes = "Joelho direito sensível"
    medicamentos = "Losartana"

    with TestClient(app) as client:
        # ------------------------------------------------------------------
        # a. LEAD CHEGA: POST /comecar with valid data + consentimento.
        # ------------------------------------------------------------------
        resp_comecar = client.post(
            "/comecar",
            data={
                "nome": nome,
                "contato": contato_valor,
                "idade": idade,
                "sexo": sexo,
                "objetivo": objetivo,
                "frequencia_desejada": frequencia_desejada,
                "nivel_condicionamento": nivel_condicionamento,
                "condicoes": condicoes,
                "lesoes": lesoes,
                "medicamentos": medicamentos,
                "consentimento": "on",
            },
        )
        assert resp_comecar.status_code == 200
        assert "Recebido!" in resp_comecar.text

        abertos_antes = list_contatos_abertos()
        assert len(abertos_antes) == 1
        lead = abertos_antes[0]
        assert lead["nome"] == nome
        assert lead["origem"] == "cadastro"
        lead_id = lead["id"]

        # ------------------------------------------------------------------
        # b. VIRA ALUNO: POST /contatos/{lead_id}/converter.
        # ------------------------------------------------------------------
        resp_converter = client.post(
            f"/contatos/{lead_id}/converter", follow_redirects=False
        )
        assert resp_converter.status_code == 303
        location = resp_converter.headers["location"]
        match = re.fullmatch(r"/alunos/(\d+)", location)
        assert match is not None
        aluno_id = int(match.group(1))

        # the lead left the open-contacts box (virou_aluno).
        abertos_depois = list_contatos_abertos()
        assert lead_id not in [c["id"] for c in abertos_depois]

        aluno = get_aluno(aluno_id)
        assert aluno is not None
        assert aluno["name"] == nome
        assert aluno["contact"] == contato_valor
        assert aluno["sex"] == sexo
        assert aluno["age_reported"] == int(idade)
        assert aluno["objective"] == objetivo
        assert aluno["weekly_frequency"] == frequencia_desejada
        assert aluno["conditioning_level"] == nivel_condicionamento
        assert aluno["health_conditions"] == condicoes
        assert aluno["restrictions"] == lesoes
        assert aluno["medications"] == medicamentos
        assert aluno["status"] == "active"

        # ------------------------------------------------------------------
        # c. FINANCEIRO: set_plano + registrar_pagamento of the current month.
        # ------------------------------------------------------------------
        set_plano(aluno_id, formato="individual", valor="300", ciclo_meses="1")

        hoje = datetime.date.today()
        registrar_pagamento(aluno_id, ano=hoje.year, mes=hoje.month, valor="300")

        panorama = panorama_mes(hoje.year, hoje.month)
        assert panorama["recebido"] >= Decimal("300")
        nomes_que_sustentam = [s["aluno_nome"] for s in panorama["sustentam"]]
        assert nome in nomes_que_sustentam

        resumo = resumo_financeiro()
        assert resumo["mrr"] >= Decimal("300")
        assert resumo["alunos_com_plano"] >= 1

        # ------------------------------------------------------------------
        # d. AVALIAÇÃO: create one, confirm it shows up in the student's
        # assessment history.
        # ------------------------------------------------------------------
        avaliacao = create_avaliacao(
            aluno_id, data=hoje.isoformat(), peso="70", altura="170"
        )
        avaliacoes = list_avaliacoes(aluno_id)
        assert len(avaliacoes) == 1
        assert avaliacoes[0]["id"] == avaliacao["id"]

        # ------------------------------------------------------------------
        # e. TREINO: an exercise, a workout and one item.
        # ------------------------------------------------------------------
        exercicio = create_exercicio(nome="Agachamento", grupo_muscular="Pernas")
        treino = create_treino(aluno_id, nome="Treino A")
        add_item_to_treino(
            treino["id"],
            exercicio_id=str(exercicio["id"]),
            series="3",
            reps="12",
        )

        treinos = list_treinos(aluno_id)
        assert len(treinos) == 1
        assert treinos[0]["id"] == treino["id"]
        assert treinos[0]["item_count"] == 1

        treino_detail = get_treino_detail(treino["id"])
        assert len(treino_detail["itens"]) == 1
        assert treino_detail["itens"][0]["exercicio_nome"] == "Agachamento"

        # ------------------------------------------------------------------
        # f. AGENDA + AUTOMAÇÃO: schedule a session with that treino, tomorrow.
        # ------------------------------------------------------------------
        amanha = hoje + datetime.timedelta(days=1)
        create_sessao(
            aluno_id,
            data=amanha.isoformat(),
            hora="07:00",
            tipo="individual",
            treino_id=str(treino["id"]),
        )

        sessoes = list_sessoes(aluno_id)
        assert len(sessoes) == 1
        assert sessoes[0]["data"] == amanha
        assert sessoes[0]["treino_id"] == treino["id"]
        assert sessoes[0]["treino_nome"] == "Treino A"

        tarefas = list_tarefas_abertas()
        contato_tarefas = [t for t in tarefas if t["categoria"] == "contato"]
        assert len(contato_tarefas) == 1
        tarefa_contato = contato_tarefas[0]
        assert tarefa_contato["titulo"] == f"Contatar {nome}"
        assert tarefa_contato["prazo"] == amanha + datetime.timedelta(days=1)
        assert tarefa_contato["concluida"] is False

        # ------------------------------------------------------------------
        # g. ACOMPANHAMENTO: log a held session, confirm it in the history.
        # ------------------------------------------------------------------
        create_sessao_realizada(
            aluno_id,
            data=hoje.isoformat(),
            presenca="compareceu",
            disposicao="boa",
            feedback="Sessão tranquila, bom ritmo.",
        )

        historico = list_sessoes_realizadas(aluno_id)
        assert len(historico) == 1
        assert historico[0]["presenca"] == "compareceu"
        assert historico[0]["data"] == hoje

        # ------------------------------------------------------------------
        # h. COERÊNCIA FINAL.
        # ------------------------------------------------------------------
        alunos_ativos = list_alunos()
        assert any(a["id"] == aluno_id for a in alunos_ativos)

        aluno_final = get_aluno(aluno_id)
        assert aluno_final["status"] == "active"

        panorama_final = panorama_mes(hoje.year, hoje.month)
        assert nome in [s["aluno_nome"] for s in panorama_final["sustentam"]]

        tarefas_finais = list_tarefas_abertas()
        assert any(
            t["titulo"] == f"Contatar {nome}"
            and t["prazo"] == amanha + datetime.timedelta(days=1)
            for t in tarefas_finais
        )
