"""Command line interface of Kairos.

Presentation layer only (architecture rule 2, thin client): it parses the
arguments, calls the integration layer (:mod:`kairos.alunos.excel_import`) and
the service layer (:mod:`kairos.alunos.service`), prints the report in
Portuguese (architecture rule 10) and defines the exit codes. No business rule
lives here: spreadsheet interpretation belongs to the integration layer, and
duplicate detection, validation and persistence belong to the service.

Usage::

    python -m kairos.cli importar-aluno "<pasta do aluno>" [--simular]
    python -m kairos.cli semear-demo [--remover]
"""

import argparse
import datetime
import logging
from typing import Dict, List, Optional, Sequence

from sqlalchemy import delete, select

from kairos.acompanhamento.models import SessaoRealizada
from kairos.acompanhamento.service import create_sessao_realizada
from kairos.agenda.models import SessaoAgendada
from kairos.agenda.service import create_sessao
from kairos.alunos.excel_import import ParsedImport, parse_aluno_folder
from kairos.alunos.models import Aluno
from kairos.alunos.service import ValidationError, create_aluno, find_aluno_by_name
from kairos.avaliacoes.models import Avaliacao, Perimetria
from kairos.avaliacoes.service import create_avaliacao
from kairos.contatos.models import Contato
from kairos.contatos.service import (
    AlunoDuplicado,
    converter_contato_em_aluno,
    create_cadastro,
)
from kairos.db import session_scope
from kairos.financeiro.models import Pagamento, PlanoAluno
from kairos.financeiro.service import registrar_pagamento, set_plano
from kairos.log import setup_logging
from kairos.migrations_runner import run_migrations
from kairos.tarefas.models import Tarefa
from kairos.treinos.models import Treino, TreinoItem
from kairos.treinos.service import (
    add_item_to_treino,
    create_exercicio,
    create_treino,
    list_exercicios,
)

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_ERROR = 1

#: Name that marks every record created by "semear-demo" as demo data, so
#: --remover can find (and only ever touch) demo rows, never real students.
DEMO_NOME = "Ana Demonstração"

#: Coach-facing labels for the recognized fields, in the order they are printed.
FIELD_LABELS = (
    ("name", "Nome"),
    ("objective", "Objetivo"),
    ("plan_start", "Início do plano"),
    ("plan_end", "Término do plano"),
)

#: Fields whose value is an ISO date and must be shown as DD/MM/AAAA.
DATE_FIELDS = ("plan_start", "plan_end")


def _format_date(value: str) -> str:
    """Show an ISO "YYYY-MM-DD" date as DD/MM/AAAA, or return it unchanged.

    A value that is not a valid ISO date is printed exactly as it came, so the
    coach sees the real content instead of a guess (architecture rule 6).
    """
    try:
        return datetime.date.fromisoformat(value).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value)


def _format_value(key: str, value: object) -> str:
    """Format a recognized field's value for display."""
    if key in DATE_FIELDS and isinstance(value, str):
        return _format_date(value)
    return str(value)


def _report_lines(folder: str, parsed: ParsedImport) -> List[str]:
    """Build the coach-facing report as a list of lines."""
    lines: List[str] = []
    lines.append(f"Pasta: {folder}")
    if parsed.source_files:
        lines.append(f"Arquivos lidos: {', '.join(parsed.source_files)}")
    else:
        lines.append("Arquivos lidos: nenhum")

    lines.append("")
    lines.append("Campos reconhecidos:")
    for key, label in FIELD_LABELS:
        if key in parsed.fields:
            lines.append(f"- {label}: {_format_value(key, parsed.fields[key])}")

    lines.append("")
    lines.append(f"Não importado ({len(parsed.not_imported)} itens):")
    for item, reason in parsed.not_imported:
        lines.append(f"- {item}: {reason}")

    if parsed.warnings:
        lines.append("")
        lines.append("Avisos:")
        for warning in parsed.warnings:
            lines.append(f"- {warning}")

    return lines


def _print_report(folder: str, parsed: ParsedImport) -> None:
    """Print the report of what was read from the folder."""
    for line in _report_lines(folder, parsed):
        print(line)


def _import_aluno(folder: str, simulate: bool) -> int:
    """Run the "importar-aluno" command and return the exit code."""
    try:
        parsed = parse_aluno_folder(folder)
    except FileNotFoundError as exc:
        # The message already comes in Portuguese from the integration layer.
        print(str(exc))
        return EXIT_ERROR

    if "name" not in parsed.fields:
        print("Nome do aluno não encontrado nas planilhas.")
        return EXIT_ERROR

    # The duplicate check needs the database, so migrations run in both modes.
    run_migrations()

    fields: Dict[str, str] = dict(parsed.fields)
    existing = find_aluno_by_name(fields["name"])
    if existing is not None:
        print(
            f'Aluno "{existing["name"]}" já existe (id={existing["id"]}). '
            "Nada foi importado."
        )
        return EXIT_OK

    _print_report(folder, parsed)

    if simulate:
        print("")
        print("Modo simulação: nada foi gravado.")
        return EXIT_OK

    try:
        created = create_aluno(**fields)
    except ValidationError as exc:
        print("")
        print(f"Erro ao importar: {exc}")
        return EXIT_ERROR

    print("")
    print(f"Aluno importado com id={created['id']}.")
    return EXIT_OK


def _remover_demo() -> Dict[str, int]:
    """Remove every record that belongs to the demo scenario, and only those.

    Filters strictly by :data:`DEMO_NOME` (Aluno.name / Contato.nome) and by
    the exact task title created for the demo student, so real data (e.g. the
    student "Marcos Anastasio" or the contact "jeffrey reis") is never
    touched.

    Uses bulk ``DELETE`` statements in an explicit child->parent order, so the
    deletes hit the database in that exact sequence and never violate a foreign
    key. This matters on PostgreSQL/Supabase, which enforces FK constraints
    (SQLite does not by default) — an ORM ``session.delete`` loop would rely on
    the unit-of-work ordering and could try to delete the Aluno before its
    dependents. Returns how many rows were removed per entity, for the report.
    """
    counts = {
        "sessoes_realizadas": 0,
        "sessoes_agendadas": 0,
        "treino_itens": 0,
        "treinos": 0,
        "perimetrias": 0,
        "avaliacoes": 0,
        "pagamentos": 0,
        "planos": 0,
        "alunos": 0,
        "contatos": 0,
        "tarefas": 0,
    }

    def _rows(result) -> int:
        return result.rowcount or 0

    with session_scope() as session:
        aluno_ids = (
            session.execute(select(Aluno.id).where(Aluno.name == DEMO_NOME))
            .scalars()
            .all()
        )

        for aluno_id in aluno_ids:
            avaliacao_ids = (
                session.execute(
                    select(Avaliacao.id).where(Avaliacao.aluno_id == aluno_id)
                )
                .scalars()
                .all()
            )
            treino_ids = (
                session.execute(
                    select(Treino.id).where(Treino.aluno_id == aluno_id)
                )
                .scalars()
                .all()
            )

            # Grandchildren first, then children, then the parent Aluno.
            if avaliacao_ids:
                counts["perimetrias"] += _rows(
                    session.execute(
                        delete(Perimetria).where(
                            Perimetria.avaliacao_id.in_(avaliacao_ids)
                        )
                    )
                )
            counts["avaliacoes"] += _rows(
                session.execute(
                    delete(Avaliacao).where(Avaliacao.aluno_id == aluno_id)
                )
            )

            if treino_ids:
                counts["treino_itens"] += _rows(
                    session.execute(
                        delete(TreinoItem).where(
                            TreinoItem.treino_id.in_(treino_ids)
                        )
                    )
                )
            counts["treinos"] += _rows(
                session.execute(delete(Treino).where(Treino.aluno_id == aluno_id))
            )

            counts["sessoes_realizadas"] += _rows(
                session.execute(
                    delete(SessaoRealizada).where(
                        SessaoRealizada.aluno_id == aluno_id
                    )
                )
            )
            counts["sessoes_agendadas"] += _rows(
                session.execute(
                    delete(SessaoAgendada).where(
                        SessaoAgendada.aluno_id == aluno_id
                    )
                )
            )
            counts["pagamentos"] += _rows(
                session.execute(
                    delete(Pagamento).where(Pagamento.aluno_id == aluno_id)
                )
            )
            counts["planos"] += _rows(
                session.execute(
                    delete(PlanoAluno).where(PlanoAluno.aluno_id == aluno_id)
                )
            )

        counts["alunos"] = _rows(
            session.execute(delete(Aluno).where(Aluno.name == DEMO_NOME))
        )
        counts["contatos"] = _rows(
            session.execute(delete(Contato).where(Contato.nome == DEMO_NOME))
        )
        counts["tarefas"] = _rows(
            session.execute(
                delete(Tarefa).where(Tarefa.titulo == f"Contatar {DEMO_NOME}")
            )
        )

    logger.info("Demo data removed: %s", counts)
    return counts


#: Coach-facing labels for the removal report, in the order they are printed.
_REMOCAO_LABELS = (
    ("sessoes_realizadas", "Sessões realizadas"),
    ("sessoes_agendadas", "Sessões agendadas"),
    ("treino_itens", "Itens de treino"),
    ("treinos", "Treinos"),
    ("perimetrias", "Medidas de perimetria"),
    ("avaliacoes", "Avaliações"),
    ("pagamentos", "Pagamentos"),
    ("planos", "Planos"),
    ("alunos", "Alunos"),
    ("contatos", "Contatos (leads)"),
    ("tarefas", "Tarefas"),
)


def _report_remocao(counts: Dict[str, int]) -> List[str]:
    """Build the coach-facing report of what --remover removed."""
    if sum(counts.values()) == 0:
        return ["Nenhum dado de demo encontrado; nada foi removido."]

    lines = ["Dados de demo removidos:"]
    for key, label in _REMOCAO_LABELS:
        if counts.get(key):
            lines.append(f"- {label}: {counts[key]}")
    return lines


def _remover_demo_command() -> int:
    """Run "semear-demo --remover" and return the exit code."""
    run_migrations()
    counts = _remover_demo()
    for line in _report_remocao(counts):
        print(line)
    return EXIT_OK


def _report_semeadura(aluno_id: int, treino_id: int) -> List[str]:
    """Build the coach-facing report of what "semear-demo" created."""
    lines = [
        f'Cenário demo criado: aluno "{DEMO_NOME}" (id={aluno_id}).',
        "",
        "Fluxo populado de ponta a ponta:",
        "- Lead cadastrada (via cadastro público) e convertida em aluno",
        "- Plano financeiro (individual, R$ 250,00/mês) e pagamento do mês registrado",
        "- Avaliação física registrada",
        f'- Treino "Treino A — Corpo inteiro" (id={treino_id}) com 1 exercício',
        '- 2 sessões agendadas, cada uma gerando a tarefa "Contatar '
        f'{DEMO_NOME}" no dia seguinte',
        "- 1 sessão realizada (acompanhamento)",
        "",
        "Onde conferir no navegador:",
        f"- Ficha do aluno: /alunos/{aluno_id}",
        "- Financeiro do mês: /financeiro",
        "- Agenda: /agenda",
        "- Início (tarefas de contato pendentes): /",
    ]
    return lines


def _semear_demo_command() -> int:
    """Run "semear-demo" (without --remover) and return the exit code."""
    run_migrations()

    # Idempotency: recreate from a clean slate every time.
    _remover_demo()

    hoje = datetime.date.today()

    try:
        lead = create_cadastro(
            nome=DEMO_NOME,
            contato="(11) 90000-0000",
            idade="34",
            sexo="feminino",
            objetivo="Voltar a treinar com constância",
            objetivos_secundarios="Melhorar sono e disposição",
            prazo_desejado="6 meses",
            frequencia_desejada="3-4",
            condicoes="nenhuma relevante",
            lesoes="tornozelo esquerdo (2023)",
            medicamentos="nenhum",
            nivel_condicionamento="iniciante",
            consentimento=True,
        )

        aluno_id = converter_contato_em_aluno(lead["id"])
        if aluno_id is None:
            print(
                "Erro ao gerar o cenário demo: a lead recém-criada não foi "
                "encontrada."
            )
            return EXIT_ERROR

        set_plano(
            aluno_id,
            formato="individual",
            valor="250.00",
            ciclo_meses="3",
            inicio=hoje.isoformat(),
        )
        registrar_pagamento(
            aluno_id,
            ano=hoje.year,
            mes=hoje.month,
            valor="250.00",
            data_pagamento=hoje.isoformat(),
        )

        create_avaliacao(
            aluno_id,
            data=hoje.isoformat(),
            peso="68.50",
            altura="165.00",
            gordura_pct="28.0",
            massa_magra="49.00",
            massa_gorda="19.50",
        )

        exercicio = next(
            (e for e in list_exercicios() if e["nome"] == "Agachamento livre"),
            None,
        )
        if exercicio is None:
            exercicio = create_exercicio(
                nome="Agachamento livre", grupo_muscular="Pernas"
            )

        treino = create_treino(aluno_id, nome="Treino A — Corpo inteiro")
        add_item_to_treino(
            treino["id"],
            exercicio_id=str(exercicio["id"]),
            series="3",
            reps="10",
            carga="Leve (adaptação)",
        )

        create_sessao(
            aluno_id,
            data=(hoje + datetime.timedelta(days=2)).isoformat(),
            hora="08:00",
            tipo="individual",
            treino_id=str(treino["id"]),
        )
        create_sessao(
            aluno_id,
            data=(hoje + datetime.timedelta(days=4)).isoformat(),
            hora="08:00",
            tipo="individual",
            treino_id=str(treino["id"]),
        )

        create_sessao_realizada(
            aluno_id,
            data=hoje.isoformat(),
            presenca="compareceu",
            disposicao="boa",
            feedback="Sessão de adaptação; aluna se sentiu bem, sem dores.",
        )
    except AlunoDuplicado as exc:
        print(
            "Erro ao gerar o cenário demo: já existe um aluno com esse nome "
            f'("{exc.aluno_existente_nome}", id={exc.aluno_existente_id}).'
        )
        return EXIT_ERROR
    except Exception as exc:
        # Every service in this flow raises its own ValidationError with a
        # ready-to-show Portuguese message (rule 10); nothing here is a raw
        # stack trace shown to the coach.
        print(f"Erro ao gerar o cenário demo: {exc}")
        return EXIT_ERROR

    for line in _report_semeadura(aluno_id, treino["id"]):
        print(line)
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with the available subcommands."""
    parser = argparse.ArgumentParser(
        prog="python -m kairos.cli",
        description="Ferramentas de linha de comando do Kairos.",
    )
    subparsers = parser.add_subparsers(dest="command")

    importer = subparsers.add_parser(
        "importar-aluno",
        help="importa um aluno a partir da pasta de planilhas dele",
        description=(
            "Lê as planilhas .xlsx da pasta do aluno e cria o cadastro com os "
            "campos reconhecidos."
        ),
    )
    importer.add_argument("pasta", help="pasta com as planilhas .xlsx do aluno")
    importer.add_argument(
        "--simular",
        action="store_true",
        help="mostra o relatório sem gravar nada",
    )

    semear = subparsers.add_parser(
        "semear-demo",
        help="popula (ou remove) um aluno-demo completo no banco de desenvolvimento",
        description=(
            f'Cria o aluno-demo "{DEMO_NOME}" com todo o funil ligado (lead, '
            "financeiro, avaliação, treino, agenda e acompanhamento), para "
            "navegar no app com dados reais de exemplo."
        ),
    )
    semear.add_argument(
        "--remover",
        action="store_true",
        help="remove só os dados de demo, preservando os dados reais",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point of the CLI; returns the process exit code."""
    setup_logging()

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_ERROR

    if args.command == "importar-aluno":
        return _import_aluno(args.pasta, args.simular)

    if args.command == "semear-demo":
        if args.remover:
            return _remover_demo_command()
        return _semear_demo_command()

    # Unreachable while argparse validates the subcommands, but never silent.
    parser.print_help()
    return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
