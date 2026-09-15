"""HTTP routes (application layer) for the panel's top-level pages.

Thin routes only: they delegate every business rule to the domain services
and render templates. Displayed texts are in Portuguese (architecture rule
10).
"""

import datetime
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.agenda.gcal import GcalError, GcalEvent, fetch_events
from kairos.agenda.service import contar_sessoes_de_hoje, sessoes_de_hoje
from kairos.alunos.service import count_alunos
from kairos.contatos.service import STATUS_LABELS, STATUS_VALIDOS, list_contatos_abertos
from kairos.financeiro.graficos import grafico_entradas_saidas, grafico_projecao
from kairos.financeiro.service import (
    panorama_mes,
    projecao_receita,
    resumo_financeiro,
    serie_entradas_saidas,
)
from kairos.tarefas.service import list_tarefas_abertas
from kairos.web import formatar_reais, templates

logger = logging.getLogger(__name__)

router = APIRouter()

# How far ahead the general (Google) agenda looks.
_AGENDA_GERAL_DIAS = 14

_WEEKDAYS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_MONTHS_PT = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]

_CATEGORIA_LABELS = {
    "lembrete": "Lembrete",
    "publicacao": "Publicação",
    "contato": "Contato",
    "campanha": "Campanha",
}

_MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _to_tarefa_display(t: Dict[str, Any]) -> Dict[str, Any]:
    """Format one of :func:`kairos.tarefas.service.list_tarefas_abertas`'s
    dicts for display in ``painel/inicio.html``."""
    return {
        "id": t["id"],
        "titulo": t["titulo"],
        "categoria_label": (
            _CATEGORIA_LABELS.get(t["categoria"]) if t["categoria"] else None
        ),
        "prazo": t["prazo"].strftime("%d/%m/%Y") if t["prazo"] else None,
        "atrasada": bool(t["prazo"] and t["prazo"] < datetime.date.today()),
    }


def _to_contato_display(c: Dict[str, Any]) -> Dict[str, Any]:
    """Format one of :func:`kairos.contatos.service.list_contatos_abertos`'s
    dicts for display in ``painel/inicio.html``."""
    return {
        "id": c["id"],
        "nome": c["nome"],
        "contato": c["contato"],
        "status": c["status"],
        "status_label": STATUS_LABELS.get(c["status"], c["status"]),
        "observacao": c["observacao"],
    }


def inicio_context(
    tarefa_error: str = None,
    tarefa_values: Dict[str, Any] = None,
    contato_error: str = None,
    contato_values: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Assemble the panel home page's template context.

    Shared between the ``GET /`` route and the "tarefas"/"contatos" routes,
    so a form error can be re-rendered on the same page (architecture rule:
    thin routes, no duplicated context assembly).
    """
    counts = count_alunos()
    counts["sessoes_hoje"] = contar_sessoes_de_hoje()
    tarefas = [_to_tarefa_display(t) for t in list_tarefas_abertas()]
    contatos = [_to_contato_display(c) for c in list_contatos_abertos()]
    status_opcoes = [(s, STATUS_LABELS[s]) for s in STATUS_VALIDOS]
    return {
        "counts": counts,
        "tarefas": tarefas,
        "tarefa_error": tarefa_error,
        "tarefa_values": tarefa_values,
        "contatos": contatos,
        "contato_error": contato_error,
        "contato_values": contato_values,
        "status_opcoes": status_opcoes,
        "mrr": formatar_reais(resumo_financeiro()["mrr"]),
    }


@router.get("/", response_class=HTMLResponse)
async def inicio(request: Request) -> HTMLResponse:
    """Render the panel's home page with the student counts overview and
    the coach's open tasks."""
    return templates.TemplateResponse(request, "painel/inicio.html", inicio_context())


@router.get("/tarefas/fragmento", response_class=HTMLResponse)
async def tarefas_fragmento(request: Request) -> HTMLResponse:
    """Render just the open tasks list (no panel shell), so the Início's
    tasks modal can refresh it via AJAX after an action."""
    tarefas = [_to_tarefa_display(t) for t in list_tarefas_abertas()]
    return templates.TemplateResponse(
        request, "painel/_tarefas_lista.html", {"tarefas": tarefas}
    )


def _to_hoje_display(s: Dict[str, Any]) -> Dict[str, Any]:
    """Format one of :func:`sessoes_de_hoje`'s dicts for display in
    ``painel/agenda.html``."""
    return {
        "aluno_id": s["aluno_id"],
        "aluno_nome": s["aluno_nome"],
        "hora": s["hora"].strftime("%H:%M"),
        "tipo_label": "Individual" if s["tipo"] == "individual" else "Grupo",
        "treino_id": s.get("treino_id"),
        "treino_nome": s.get("treino_nome"),
    }


@router.get("/agenda", response_class=HTMLResponse)
async def agenda_hoje(request: Request) -> HTMLResponse:
    """Render today's global agenda across all students (Kairos database)."""
    sessoes = [_to_hoje_display(s) for s in sessoes_de_hoje()]
    return templates.TemplateResponse(
        request, "painel/agenda.html", {"sessoes": sessoes, "subtab": "hoje"}
    )


def _event_date(event: GcalEvent) -> datetime.date:
    """The calendar date an occurrence belongs to (date for all-day, else the
    date part of the timed start)."""
    start = event.start
    return start.date() if isinstance(start, datetime.datetime) else start


def _to_gcal_display(event: GcalEvent) -> Dict[str, Any]:
    """Format one Google Calendar occurrence for display."""
    return {
        "hora": "dia inteiro" if event.all_day else event.start.strftime("%H:%M"),
        "all_day": event.all_day,
        "summary": event.summary,
        "location": event.location,
    }


def _group_por_dia(eventos: List[GcalEvent]) -> List[Dict[str, Any]]:
    """Group chronologically-sorted occurrences into day sections."""
    grupos: List[Dict[str, Any]] = []
    for event in eventos:
        dia = _event_date(event)
        if not grupos or grupos[-1]["_data"] != dia:
            grupos.append(
                {
                    "_data": dia,
                    "data_label": (
                        f"{_WEEKDAYS_PT[dia.weekday()]}, "
                        f"{dia.day} {_MONTHS_PT[dia.month - 1]}"
                    ),
                    "eventos": [],
                }
            )
        grupos[-1]["eventos"].append(_to_gcal_display(event))
    return grupos


@router.get("/agenda/google", response_class=HTMLResponse)
async def agenda_google(request: Request) -> HTMLResponse:
    """Render the general agenda: the coach's Google Calendar (read-only).

    Shows the next :data:`_AGENDA_GERAL_DIAS` days. When no calendar is
    configured, shows a setup state; when the feed can't be read, a friendly
    error state -- never invented events (rule 6).
    """
    from kairos import config

    if not config.gcal_ics_url():
        return templates.TemplateResponse(
            request,
            "painel/agenda_google.html",
            {"subtab": "google", "state": "nao_configurado"},
        )

    hoje = datetime.date.today()
    fim = hoje + datetime.timedelta(days=_AGENDA_GERAL_DIAS)
    try:
        eventos = fetch_events(hoje, fim)
    except GcalError:
        logger.exception("Falha ao ler o Google Calendar do coach")
        return templates.TemplateResponse(
            request,
            "painel/agenda_google.html",
            {"subtab": "google", "state": "erro"},
            status_code=status.HTTP_502_BAD_GATEWAY,
        )

    return templates.TemplateResponse(
        request,
        "painel/agenda_google.html",
        {
            "subtab": "google",
            "state": "ok",
            "dias": _group_por_dia(eventos),
            "total": len(eventos),
            "janela_dias": _AGENDA_GERAL_DIAS,
        },
    )


@router.get("/avaliacao-inicial")
async def avaliacao_inicial() -> RedirectResponse:
    """A Avaliação Inicial deixou de ser área própria: agora vive no Início
    (acompanhamento de contatos). Redireciona para lá."""
    return RedirectResponse(
        url="/", status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@router.get("/financeiro", response_class=HTMLResponse)
async def financeiro(request: Request) -> HTMLResponse:
    """Render the "Financeiro" area with the current month's panorama
    (result, received, expenses, receivables, MRR, average ticket and the
    students who sustain the business)."""
    hoje = datetime.date.today()
    p = panorama_mes(hoje.year, hoje.month)
    context = {
        "mes_label": f"{_MESES[hoje.month - 1]} {hoje.year}",
        "resultado": formatar_reais(p["resultado"]),
        "resultado_positivo": p["resultado"] >= 0,
        "recebido": formatar_reais(p["recebido"]),
        "despesas": formatar_reais(p["despesas"]),
        "a_receber": formatar_reais(p["a_receber"]),
        "mrr": formatar_reais(p["mrr"]),
        "ticket_medio": formatar_reais(p["ticket_medio"]),
        "alunos_com_plano": p["alunos_com_plano"],
        "sustentam": [
            {"aluno_nome": s["aluno_nome"], "valor": formatar_reais(s["valor_pago"])}
            for s in p["sustentam"]
        ],
        "g_entradas": grafico_entradas_saidas(serie_entradas_saidas(6)),
        "g_projecao": grafico_projecao(projecao_receita(6)),
    }
    return templates.TemplateResponse(request, "painel/financeiro.html", context)


@router.get("/conteudo", response_class=HTMLResponse)
async def conteudo(request: Request) -> HTMLResponse:
    """Render the placeholder page for the "Conteúdo & Comunicação" area."""
    return templates.TemplateResponse(
        request,
        "painel/area_em_breve.html",
        {
            "title": "Conteúdo & Comunicação",
            "eyebrow": "Conteúdo + comunicação",
            "items": [
                {
                    "name": "Biblioteca",
                    "desc": "As 3 séries, ebooks, artigos e publicações criados para os alunos.",
                },
                {
                    "name": "Newsletter",
                    "desc": "As edições e os envios.",
                },
                {
                    "name": "Comunicação com alunos",
                    "desc": "Enviar conteúdo e mensagens; futuramente WhatsApp/e-mail.",
                },
            ],
        },
    )
