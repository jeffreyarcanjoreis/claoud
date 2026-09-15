"""Tests for issue 02 (server-rendered SVG evolution chart).

Covers the functional specification:
- 0 assessments -> empty-state message, no chart SVG;
- 2 assessments (with peso) -> the chart SVG exists, the list and the chart
  panel coexist, and the "peso" metric group is visible with 2 dots and a
  connecting line;
- the 4 metric groups (peso, massa_magra, gordura_pct, imc) are always
  present in the HTML, only "peso" without the display:none marker;
- 1 assessment -> a single dot, no polyline (no line for a lone point);
- a NULL metric value creates a gap: that metric's group has fewer drawn
  points than a fully-populated metric (or "no data" text if every value is
  missing);
- regression: the assessments list keeps showing its previous fields (date,
  peso) alongside the new chart.

These are structural checks (element/marker counts), not pixel-exact
geometry — see the module-level helper below for how a single metric's
<g data-metric="..."> group is isolated from the rest of the SVG markup.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.avaliacoes.service import create_avaliacao
from kairos.main import app

# The <svg> carries this class regardless of its other attributes' order
# (e.g. viewBox comes first in the actual markup); checking the class alone
# keeps this test decoupled from attribute ordering, which is not part of
# the observable behaviour.
CHART_SVG_MARKER = 'class="evolucao-chart"'


def _metric_group(html: str, key: str) -> str:
    """Extract the HTML slice for one metric's <g data-metric="key"> group.

    Slices from the group's ``data-metric="key"`` marker up to the next
    ``data-metric=`` marker (the following metric group), or to the end of
    the string if it is the last one. This lets a test count dots/lines
    scoped to a single metric without parsing the SVG as XML.
    """
    marker = f'data-metric="{key}"'
    start = html.index(marker)
    next_marker_pos = html.find("data-metric=", start + len(marker))
    end = next_marker_pos if next_marker_pos != -1 else len(html)
    return html[start:end]


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_zero_assessments_shows_empty_chart_state_and_no_svg(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    assert "Sem dados para o gráfico." in response.text
    assert CHART_SVG_MARKER not in response.text


def test_two_assessments_render_chart_svg_alongside_the_list(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="70")
        create_avaliacao(aluno["id"], data="2026-02-10", peso="68")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    assert CHART_SVG_MARKER in text
    # the two-column layout: list on the left, chart panel on the right.
    assert "avaliacoes-layout" in text
    assert "avaliacoes-lista" in text
    assert "chart-panel" in text

    peso_group = _metric_group(text, "peso")
    assert "display:none" not in peso_group
    assert peso_group.count("chart-dot") == 2
    assert peso_group.count("chart-line") >= 1


def test_all_four_metric_groups_present_only_peso_visible(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="70")
        create_avaliacao(aluno["id"], data="2026-02-10", peso="68")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    for key in ("peso", "massa_magra", "gordura_pct", "imc"):
        assert f'data-metric="{key}"' in text

    peso_group = _metric_group(text, "peso")
    assert "display:none" not in peso_group

    for key in ("massa_magra", "gordura_pct", "imc"):
        group = _metric_group(text, key)
        assert "display:none" in group, f"metric {key} should start hidden"


def test_single_assessment_renders_one_dot_and_no_line(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="70")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    assert CHART_SVG_MARKER in text

    peso_group = _metric_group(text, "peso")
    assert peso_group.count("chart-dot") == 1
    assert "<polyline" not in peso_group


def test_null_metric_value_leaves_a_gap_with_fewer_points_than_peso(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(
            aluno["id"], data="2026-01-10", peso="70", massa_magra="55"
        )
        # second assessment has peso but no massa_magra (NULL) -> a gap in
        # the massa_magra series, while peso keeps both points.
        create_avaliacao(aluno["id"], data="2026-02-10", peso="68")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    peso_group = _metric_group(text, "peso")
    massa_group = _metric_group(text, "massa_magra")

    assert peso_group.count("chart-dot") == 2
    assert massa_group.count("chart-dot") == 1
    assert massa_group.count("chart-dot") < peso_group.count("chart-dot")
    # a single non-None value never yields a connecting segment.
    assert "<polyline" not in massa_group


def test_metric_group_shows_no_data_message_when_all_values_are_null(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="70")
        create_avaliacao(aluno["id"], data="2026-02-10", peso="68")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    massa_group = _metric_group(text, "massa_magra")
    assert "Sem dados para esta métrica." in massa_group
    assert massa_group.count("chart-dot") == 0


def test_list_still_shows_date_and_peso_alongside_the_chart(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="70")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    assert "10/01/2026" in text
    assert "70" in text
