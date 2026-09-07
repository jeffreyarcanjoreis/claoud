"""HTTP routes (application layer) for the "avaliacoes" (student assessments)
domain.

Thin routes only: they collect data, delegate every business rule to
:mod:`kairos.avaliacoes.service`, and render templates. Displayed texts are
in Portuguese (architecture rule 10).
"""

import decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from kairos.alunos.service import get_aluno
from kairos.avaliacoes.service import (
    PERIMETRIA_SEGMENTOS,
    ValidationError,
    avaliacao_series,
    create_avaliacao,
    get_avaliacao_detail,
    list_avaliacoes,
)
from kairos.web import ficha_header, templates

router = APIRouter()

_NO_RECORD = "sem registro"

# SVG viewBox and plot-area geometry for the "Avaliações físicas" evolution
# chart (issue 02). Margins reserve room for Y-axis value labels (left) and
# X-axis date labels (bottom); top/right keep a small breathing gap.
_CHART_VB_W = 480
_CHART_VB_H = 300
_CHART_MARGIN_LEFT = 46
_CHART_MARGIN_RIGHT = 14
_CHART_MARGIN_TOP = 14
_CHART_MARGIN_BOTTOM = 34

# (field, display label, CSS class, initially visible) for the four metrics
# plotted on the chart, in the fixed order the coach expects to toggle them.
# Only "peso" starts visible; the others are opt-in via the legend (issue 03).
_CHART_METRICS = (
    ("peso", "Peso (kg)", "line-peso", True),
    ("massa_magra", "Massa magra (kg)", "line-massa-magra", False),
    ("gordura_pct", "% Gordura", "line-gordura", False),
    ("imc", "IMC", "line-imc", False),
)

# (field, display label) for the five metrics shown on the detail page, in the
# fixed order the coach expects to read them.
_METRIC_DISPLAY = (
    ("peso", "Peso (kg)"),
    ("altura", "Altura (cm)"),
    ("gordura_pct", "% Gordura"),
    ("massa_magra", "Massa magra (kg)"),
    ("massa_gorda", "Massa gorda (kg)"),
)


def _to_list_display(av: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer avaliacao dict to ready-to-print list fields."""
    return {
        "id": av["id"],
        "data": av["data"].strftime("%d/%m/%Y"),
        "peso": str(av["peso"]) if av["peso"] is not None else _NO_RECORD,
        "gordura_pct": (
            str(av["gordura_pct"]) if av["gordura_pct"] is not None else _NO_RECORD
        ),
    }


def _format_valor(value: Optional[decimal.Decimal]) -> str:
    """Format a metric value in Brazilian notation (comma decimal), or "sem registro"."""
    if value is None:
        return _NO_RECORD
    return str(value).replace(".", ",")


def _build_chart(series: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute the SVG geometry for the "Avaliações físicas" evolution chart.

    ``series`` is the chronological (ascending) list returned by
    :func:`kairos.avaliacoes.service.avaliacao_series`. Coordinates are
    floats placed in a fixed 480x300 viewBox; displayed values keep the
    Brazilian (comma-decimal) formatting of the stored Decimals (rule 10) —
    floats are only used for pixel geometry, never for what is printed.
    Missing values (None) are never faked (rule 6): a metric with no data
    renders no points and no segments, and a run of points is broken across
    any None gap.
    """
    n = len(series)
    plot_left = _CHART_MARGIN_LEFT
    plot_right = _CHART_VB_W - _CHART_MARGIN_RIGHT
    plot_top = _CHART_MARGIN_TOP
    plot_bottom = _CHART_VB_H - _CHART_MARGIN_BOTTOM

    if n == 0:
        x_positions: List[float] = []
    elif n == 1:
        x_positions = [(plot_left + plot_right) / 2]
    else:
        step = (plot_right - plot_left) / (n - 1)
        x_positions = [plot_left + i * step for i in range(n)]

    x_labels = [
        {"x": x_positions[i], "text": series[i]["data"].strftime("%d/%m")}
        for i in range(n)
    ]

    metrics = [
        _build_metric_chart(key, label, css, visible, series, x_positions, plot_top, plot_bottom)
        for key, label, css, visible in _CHART_METRICS
    ]

    return {
        "empty": n == 0,
        "vb_w": _CHART_VB_W,
        "vb_h": _CHART_VB_H,
        "x_labels": x_labels,
        "metrics": metrics,
    }


def _build_metric_chart(
    key: str,
    label: str,
    css: str,
    visible: bool,
    series: List[Dict[str, Any]],
    x_positions: List[float],
    plot_top: float,
    plot_bottom: float,
) -> Dict[str, Any]:
    """Compute one metric's Y-scale, value points and polyline segments.

    The Y-scale uses only that metric's non-None values (min/max with ~8%
    padding), inverted so a larger value sits higher on the chart. When
    there is a single non-None value, or all non-None values are equal, the
    scale would divide by zero — instead every such point is placed on the
    vertical middle of the plot area.
    """
    indexed = [(i, av[key]) for i, av in enumerate(series) if av[key] is not None]
    no_data = len(indexed) == 0
    single = len(indexed) == 1

    if no_data:
        return {
            "key": key,
            "label": label,
            "css": css,
            "visible": visible,
            "no_data": True,
            "single": False,
            "y_labels": [],
            "points": [],
            "segments": [],
        }

    values = [v for _, v in indexed]
    vmin, vmax = min(values), max(values)

    if single or vmin == vmax:
        y_mid = (plot_top + plot_bottom) / 2

        def y_for(_value: decimal.Decimal, _y_mid: float = y_mid) -> float:
            return _y_mid

        y_labels = [{"y": y_mid, "text": _format_valor(values[0])}]
    else:
        pad = (vmax - vmin) * decimal.Decimal("0.08")
        lo = float(vmin - pad)
        hi = float(vmax + pad)
        span = hi - lo

        def y_for(value: decimal.Decimal, _lo: float = lo, _span: float = span) -> float:
            return plot_bottom - (float(value) - _lo) / _span * (plot_bottom - plot_top)

        mid_value = (vmin + vmax) / decimal.Decimal(2)
        y_labels = [
            {"y": round(y_for(vmax), 2), "text": _format_valor(vmax)},
            {"y": round(y_for(mid_value), 2), "text": _format_valor(mid_value)},
            {"y": round(y_for(vmin), 2), "text": _format_valor(vmin)},
        ]

    points = [
        {
            "x": round(x_positions[i], 2),
            "y": round(y_for(av[key]), 2),
            "value": _format_valor(av[key]),
        }
        for i, av in enumerate(series)
        if av[key] is not None
    ]

    segments: List[str] = []
    current_run: List[str] = []
    for i, av in enumerate(series):
        if av[key] is not None:
            current_run.append(f"{round(x_positions[i], 2)},{round(y_for(av[key]), 2)}")
        else:
            if len(current_run) >= 2:
                segments.append(" ".join(current_run))
            current_run = []
    if len(current_run) >= 2:
        segments.append(" ".join(current_run))

    return {
        "key": key,
        "label": label,
        "css": css,
        "visible": visible,
        "no_data": False,
        "single": single,
        "y_labels": y_labels,
        "points": points,
        "segments": segments,
    }


def _format_delta(
    delta: Optional[decimal.Decimal],
) -> Tuple[Optional[str], Optional[str]]:
    """Format a metric's delta with sign, plus its "direcao" for the template.

    Returns ``(None, None)`` when there is no previous assessment to compare
    against. Zero renders as the literal "0" with direction "same".
    """
    if delta is None:
        return None, None
    if delta == 0:
        return "0", "same"
    if delta > 0:
        return f"+{str(delta).replace('.', ',')}", "up"
    magnitude = str(-delta).replace(".", ",")
    return f"−{magnitude}", "down"


def _to_detail_display(detalhe: Dict[str, Any]) -> Dict[str, Any]:
    """Map a service-layer avaliacao detail dict to ready-to-print detail fields."""
    metricas = []
    for field, label in _METRIC_DISPLAY:
        delta_str, direcao = _format_delta(detalhe["deltas"][field])
        metricas.append(
            {
                "label": label,
                "valor": _format_valor(detalhe[field]),
                "delta": delta_str,
                "direcao": direcao,
            }
        )

    perimetria_display = []
    for p in detalhe.get("perimetria", []):
        valor_str = _format_valor(p["valor"])
        delta_str, direcao = _format_delta(p["delta"])
        perimetria_display.append(
            {
                "label": p["segmento"],
                "valor": valor_str,
                "delta": delta_str,
                "direcao": direcao,
            }
        )

    return {
        "data": detalhe["data"].strftime("%d/%m/%Y"),
        "metricas": metricas,
        "imc": _format_valor(detalhe["imc"]),
        "has_previous": detalhe["has_previous"],
        "perimetria": perimetria_display,
    }


@router.get("/alunos/{aluno_id}/avaliacoes", response_class=HTMLResponse)
async def aluno_avaliacoes(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the student's "Avaliações físicas" sub-tab, or a 404 page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    avals = list_avaliacoes(aluno_id)
    series = avaliacao_series(aluno_id)
    context = {
        "aluno": ficha_header(aluno),
        "subtab": "avaliacoes",
        "avaliacoes": [_to_list_display(av) for av in avals],
        "chart": _build_chart(series),
    }
    return templates.TemplateResponse(request, "avaliacoes/lista.html", context)


# Declared before any future "/alunos/{aluno_id}/avaliacoes/{avaliacao_id}" route
# (issue 05): the literal "nova" segment must win over the parameterized one
# (route registration order matters in FastAPI).
@router.get("/alunos/{aluno_id}/avaliacoes/nova", response_class=HTMLResponse)
async def new_avaliacao_form(request: Request, aluno_id: int) -> HTMLResponse:
    """Render the new assessment form, or a 404 page when the student is absent."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return templates.TemplateResponse(
        request,
        "avaliacoes/nova.html",
        {
            "aluno": ficha_header(aluno),
            "subtab": "avaliacoes",
            "segmentos": PERIMETRIA_SEGMENTOS,
        },
    )


# Registered after "/alunos/{aluno_id}/avaliacoes/nova": FastAPI matches
# routes in registration order, and "avaliacao_id: int" would never match the
# literal "nova" segment anyway — but the order is kept for clarity (issue 05).
@router.get(
    "/alunos/{aluno_id}/avaliacoes/{avaliacao_id}", response_class=HTMLResponse
)
async def avaliacao_detail(
    request: Request, aluno_id: int, avaliacao_id: int
) -> HTMLResponse:
    """Render a single assessment's detail (deltas and BMI), or a 404 page."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    detalhe = get_avaliacao_detail(avaliacao_id)
    if detalhe is None or detalhe["aluno_id"] != aluno_id:
        # Also covers an avaliacao_id that belongs to a different aluno, so a
        # coach cannot browse another student's assessment via the URL.
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return templates.TemplateResponse(
        request,
        "avaliacoes/detalhe.html",
        {
            "aluno": ficha_header(aluno),
            "subtab": "avaliacoes",
            "av": _to_detail_display(detalhe),
        },
    )


@router.post("/alunos/{aluno_id}/avaliacoes")
async def create_avaliacao_route(
    request: Request,
    aluno_id: int,
    data: Optional[str] = Form(None),
    peso: Optional[str] = Form(None),
    altura: Optional[str] = Form(None),
    gordura_pct: Optional[str] = Form(None),
    massa_magra: Optional[str] = Form(None),
    massa_gorda: Optional[str] = Form(None),
):
    """Create an assessment via the service layer; no business rules here."""
    aluno = get_aluno(aluno_id)
    if aluno is None:
        return templates.TemplateResponse(
            request,
            "alunos/nao_encontrado.html",
            {},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    form = await request.form()
    perimetria = {key: form.get("perim_" + key) for key, _label in PERIMETRIA_SEGMENTOS}

    try:
        create_avaliacao(
            aluno_id,
            data=data,
            peso=peso,
            altura=altura,
            gordura_pct=gordura_pct,
            massa_magra=massa_magra,
            massa_gorda=massa_gorda,
            perimetria=perimetria,
        )
    except ValidationError as exc:
        values = {
            "data": data,
            "peso": peso,
            "altura": altura,
            "gordura_pct": gordura_pct,
            "massa_magra": massa_magra,
            "massa_gorda": massa_gorda,
            "perimetria": perimetria,
        }
        return templates.TemplateResponse(
            request,
            "avaliacoes/nova.html",
            {
                "aluno": ficha_header(aluno),
                "subtab": "avaliacoes",
                "segmentos": PERIMETRIA_SEGMENTOS,
                "error": str(exc),
                "values": values,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=f"/alunos/{aluno_id}/avaliacoes",
        status_code=status.HTTP_303_SEE_OTHER,
    )
