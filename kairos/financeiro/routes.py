"""HTTP routes (application layer) for the "financeiro" (student plan &
value) domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.financeiro.service`, and render templates. Displayed texts are
in Portuguese (architecture rule 10).
"""

import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.alunos.service import get_aluno
from kairos.financeiro.service import (
    ValidationError,
    despesas_do_mes,
    get_plano,
    pagamentos_do_aluno,
    recebimentos_do_mes,
    registrar_despesa,
    registrar_pagamento,
    remover_despesa,
    remover_pagamento,
    remover_plano,
    resumo_recebimentos_mes,
    set_plano,
    total_despesas_mes,
)
from kairos.web import ficha_header, formatar_reais, templates

router = APIRouter()

_FORMATO_LABELS = {
    "digital": "Digital",
    "grupo": "Grupo",
    "individual": "Individual (1-a-1)",
}

_CATEGORIA_DESPESA_LABELS = {
    "aluguel": "Aluguel",
    "equipamento": "Equipamento",
    "software": "Software",
    "divulgacao": "Divulgação",
    "formacao": "Formação",
    "outros": "Outros",
}

_MESES_PT = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


def _to_plano_display(p: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer plano dict to ready-to-print display fields."""
    return {
        "formato_label": _FORMATO_LABELS.get(p["formato"], p["formato"]),
        "valor": formatar_reais(p["valor"]),
        "ciclo": (
            f'{p["ciclo_meses"]} meses' if p["ciclo_meses"] else "sem registro"
        ),
        "inicio": (
            p["inicio"].strftime("%d/%m/%Y") if p["inicio"] else "sem registro"
        ),
        "observacao": p["observacao"] or None,
    }


def _to_pagamento_display(p: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer pagamento dict to ready-to-print display fields."""
    return {
        "competencia": f'{p["mes"]:02d}/{p["ano"]}',
        "valor": formatar_reais(p["valor"]),
        "data": (
            p["data_pagamento"].strftime("%d/%m/%Y")
            if p["data_pagamento"]
            else "sem registro"
        ),
    }


def _to_recebimento_linha(r: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer recebimento-do-mes dict to display fields."""
    return {
        "aluno_id": r["aluno_id"],
        "aluno_nome": r["aluno_nome"],
        "valor_plano": formatar_reais(r["valor_plano"]),
        "valor_plano_input": str(r["valor_plano"]),
        "pago": r["pago"],
        "pagamento_id": r["pagamento_id"],
        "valor_pago": formatar_reais(r["valor_pago"]) if r["pago"] else None,
        "data_pagamento": (
            r["data_pagamento"].strftime("%d/%m/%Y") if r["data_pagamento"] else None
        ),
    }


def _contexto_recebimentos(error: Optional[str] = None) -> Dict[str, Any]:
    """Build the context for the month's "Recebimentos" panel page."""
    hoje = datetime.date.today()
    ano, mes = hoje.year, hoje.month
    r = resumo_recebimentos_mes(ano, mes)
    return {
        "mes_label": f"{_MESES_PT[mes - 1]} {ano}",
        "resumo": {
            "recebido": formatar_reais(r["recebido"]),
            "pendente": formatar_reais(r["pendente"]),
        },
        "linhas": [_to_recebimento_linha(x) for x in recebimentos_do_mes(ano, mes)],
        "hoje": hoje.isoformat(),
        "error": error,
    }


def _to_despesa_display(d: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer despesa dict to ready-to-print display fields."""
    return {
        "id": d["id"],
        "data": d["data"].strftime("%d/%m/%Y"),
        "descricao": d["descricao"],
        "categoria_label": (
            _CATEGORIA_DESPESA_LABELS.get(d["categoria"]) if d["categoria"] else None
        ),
        "valor": formatar_reais(d["valor"]),
    }


def _contexto_despesas(
    error: Optional[str] = None, values: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build the context for the month's "Despesas" panel page."""
    hoje = datetime.date.today()
    ano, mes = hoje.year, hoje.month
    return {
        "mes_label": f"{_MESES_PT[mes - 1]} {ano}",
        "total": formatar_reais(total_despesas_mes(ano, mes)),
        "despesas": [_to_despesa_display(x) for x in despesas_do_mes(ano, mes)],
        "hoje": hoje.isoformat(),
        "error": error,
        "values": values,
    }


@router.get("/alunos/{aluno_id}/financeiro", response_class=HTMLResponse)
async def aluno_financeiro(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the student's "Financeiro" sub-tab, or a 404 page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    plano = get_plano(aluno_id)
    context = {
        "aluno": ficha_header(aluno),
        "subtab": "financeiro",
        "plano": _to_plano_display(plano) if plano else None,
        "pagamentos": [_to_pagamento_display(p) for p in pagamentos_do_aluno(aluno_id)],
    }
    return templates.TemplateResponse(request, "alunos/financeiro.html", context)


@router.post("/alunos/{aluno_id}/financeiro")
async def set_plano_route(
    request: Request,
    aluno_id: int,
    formato: Optional[str] = Form(None),
    valor: Optional[str] = Form(None),
    ciclo_meses: Optional[str] = Form(None),
    inicio: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
):
    """Create or update the student's plan via the service layer; no
    business rules here."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        set_plano(
            aluno_id,
            formato=formato,
            valor=valor,
            ciclo_meses=ciclo_meses,
            inicio=inicio,
            observacao=observacao,
        )
    except ValidationError as exc:
        plano = get_plano(aluno_id)
        values = {
            "formato": formato,
            "valor": valor,
            "ciclo_meses": ciclo_meses,
            "inicio": inicio,
            "observacao": observacao,
        }
        return templates.TemplateResponse(
            request,
            "alunos/financeiro.html",
            {
                "aluno": ficha_header(aluno),
                "subtab": "financeiro",
                "plano": _to_plano_display(plano) if plano else None,
                "pagamentos": [
                    _to_pagamento_display(p) for p in pagamentos_do_aluno(aluno_id)
                ],
                "error": str(exc),
                "values": values,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/financeiro",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/alunos/{aluno_id}/financeiro/remover")
async def remover_plano_route(request: Request, aluno_id: int):
    """Remove the student's plan via the service layer."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    remover_plano(aluno_id)

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/financeiro",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/financeiro/recebimentos", response_class=HTMLResponse)
async def recebimentos(request: Request) -> HTMLResponse:
    """Render the current month's "Recebimentos" panel page."""
    return templates.TemplateResponse(
        request, "painel/recebimentos.html", _contexto_recebimentos()
    )


@router.post("/financeiro/recebimentos")
async def registrar_pagamento_route(
    request: Request,
    aluno_id: str = Form(...),
    valor: Optional[str] = Form(None),
    data_pagamento: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
):
    """Register a payment for the current month via the service layer."""
    hoje = datetime.date.today()
    try:
        registrar_pagamento(
            int(aluno_id),
            ano=hoje.year,
            mes=hoje.month,
            valor=valor,
            data_pagamento=data_pagamento,
            observacao=observacao,
        )
    except (ValidationError, ValueError) as exc:
        return templates.TemplateResponse(
            request,
            "painel/recebimentos.html",
            _contexto_recebimentos(error=str(exc)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url="/financeiro/recebimentos",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/financeiro/recebimentos/{pagamento_id}/remover")
async def remover_pagamento_route(request: Request, pagamento_id: int):
    """Remove a payment via the service layer."""
    remover_pagamento(pagamento_id)

    return RedirectResponse(
        url="/financeiro/recebimentos",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/financeiro/despesas", response_class=HTMLResponse)
async def despesas(request: Request) -> HTMLResponse:
    """Render the current month's "Despesas" panel page."""
    return templates.TemplateResponse(
        request, "painel/despesas.html", _contexto_despesas()
    )


@router.post("/financeiro/despesas")
async def registrar_despesa_route(
    request: Request,
    data: Optional[str] = Form(None),
    descricao: Optional[str] = Form(None),
    categoria: Optional[str] = Form(None),
    valor: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
):
    """Register an expense for the current month via the service layer."""
    try:
        registrar_despesa(
            data=data,
            descricao=descricao,
            categoria=categoria,
            valor=valor,
            observacao=observacao,
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "painel/despesas.html",
            _contexto_despesas(
                error=str(exc),
                values={
                    "data": data,
                    "descricao": descricao,
                    "categoria": categoria,
                    "valor": valor,
                },
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url="/financeiro/despesas",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/financeiro/despesas/{despesa_id}/remover")
async def remover_despesa_route(request: Request, despesa_id: int):
    """Remove an expense via the service layer."""
    remover_despesa(despesa_id)

    return RedirectResponse(
        url="/financeiro/despesas",
        status_code=status.HTTP_303_SEE_OTHER,
    )
