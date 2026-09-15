"""Presentation helpers: turn financial series into SVG chart geometry.

Pure functions (no database). They receive the series produced by
:mod:`kairos.financeiro.service` and return dictionaries of coordinates for the
server-rendered SVG in ``painel/financeiro.html`` — the same pattern as
``kairos.avaliacoes.routes._build_chart``. No external chart library (CSP): the
template draws plain ``<rect>``/``<polyline>`` with native ``<title>`` tooltips.

Colours are set in CSS by series class (``.serie-entrada`` blue, ``.serie-saida``
orange — a colourblind-safe pair validated with the dataviz palette script;
``.serie-projecao`` gold). Identity never rests on colour alone: a legend and
axis labels accompany every chart.
"""

from decimal import Decimal
from typing import Any, Dict, List

from kairos.web import formatar_reais

_VB_W = 480


def _mes_label(ano: int, mes: int) -> str:
    """Short axis label like ``08/26``."""
    return f"{mes:02d}/{str(ano)[-2:]}"


def grafico_entradas_saidas(serie: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Grouped bars per month: entradas (recebido) vs saídas (despesas).

    ``serie`` is oldest→newest, each item ``{ano, mes, recebido, despesas}``.
    A month with no data reads as a zero-height bar; when the whole window is
    zero the chart reports ``empty`` so the template shows an honest note
    instead of an empty axis (rule 6).
    """
    vb_h = 260
    left, right, top, bottom = 60, 12, 16, 30
    plot_left, plot_right = left, _VB_W - right
    plot_top, plot_bottom = top, vb_h - bottom
    plot_w = plot_right - plot_left
    plot_h = plot_bottom - plot_top

    n = len(serie)
    max_dec = max(
        (max(m["recebido"], m["despesas"]) for m in serie), default=Decimal("0")
    )
    max_val = float(max_dec)
    empty = n == 0 or max_val <= 0

    bars: List[Dict[str, Any]] = []
    x_labels: List[Dict[str, Any]] = []
    if not empty:
        group_w = plot_w / n
        bar_w = min(group_w * 0.30, 20)
        gap = 3
        pair_w = bar_w * 2 + gap
        for i, m in enumerate(serie):
            gx = plot_left + group_w * (i + 0.5)
            x_labels.append({"x": round(gx, 1), "text": _mes_label(m["ano"], m["mes"])})
            start_x = gx - pair_w / 2
            for j, (serie_key, label, val) in enumerate(
                (("entrada", "Entradas", m["recebido"]), ("saida", "Saídas", m["despesas"]))
            ):
                h = (float(val) / max_val) * plot_h
                x = start_x + j * (bar_w + gap)
                bars.append(
                    {
                        "x": round(x, 1),
                        "y": round(plot_bottom - h, 1),
                        "w": round(bar_w, 1),
                        "h": round(h, 1),
                        "serie": serie_key,
                        "titulo": (
                            f"{_mes_label(m['ano'], m['mes'])} · {label}: "
                            f"{formatar_reais(val)}"
                        ),
                    }
                )

    y_ticks = (
        []
        if empty
        else [
            {"y": round(plot_bottom, 1), "text": "R$ 0"},
            {"y": round(plot_top, 1), "text": formatar_reais(max_dec)},
        ]
    )

    return {
        "empty": empty,
        "vb_w": _VB_W,
        "vb_h": vb_h,
        "baseline_y": round(plot_bottom, 1),
        "plot_left": plot_left,
        "plot_right": plot_right,
        "bars": bars,
        "x_labels": x_labels,
        "y_ticks": y_ticks,
    }


def grafico_projecao(serie: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Line of projected recurring revenue for the coming months.

    ``serie`` is nearest→farthest, each item ``{ano, mes, receita, alunos}``.
    Single series (gold); the projected paying-student count rides along as a
    per-month label, never a second y-axis (dataviz: one axis only). Empty when
    there is no active plan to project.
    """
    vb_h = 220
    left, right, top, bottom = 60, 14, 16, 40
    plot_left, plot_right = left, _VB_W - right
    plot_top, plot_bottom = top, vb_h - bottom
    plot_w = plot_right - plot_left
    plot_h = plot_bottom - plot_top

    n = len(serie)
    max_dec = max((m["receita"] for m in serie), default=Decimal("0"))
    max_val = float(max_dec)
    empty = n == 0 or max_val <= 0

    points: List[Dict[str, Any]] = []
    x_labels: List[Dict[str, Any]] = []
    if not empty:
        for i, m in enumerate(serie):
            x = plot_left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)
            y = plot_bottom - (float(m["receita"]) / max_val) * plot_h
            points.append(
                {
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "titulo": (
                        f"{_mes_label(m['ano'], m['mes'])}: {formatar_reais(m['receita'])}"
                        f" · {m['alunos']} aluno(s)"
                    ),
                }
            )
            x_labels.append(
                {
                    "x": round(x, 1),
                    "text": _mes_label(m["ano"], m["mes"]),
                    "alunos": m["alunos"],
                }
            )

    y_ticks = (
        []
        if empty
        else [
            {"y": round(plot_bottom, 1), "text": "R$ 0"},
            {"y": round(plot_top, 1), "text": formatar_reais(max_dec)},
        ]
    )

    return {
        "empty": empty,
        "vb_w": _VB_W,
        "vb_h": vb_h,
        "baseline_y": round(plot_bottom, 1),
        "plot_left": plot_left,
        "plot_right": plot_right,
        "points": points,
        "polyline": " ".join(f"{p['x']},{p['y']}" for p in points),
        "x_labels": x_labels,
        "y_ticks": y_ticks,
    }
