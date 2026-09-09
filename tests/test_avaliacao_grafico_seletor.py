"""Tests for issue 03 (metric selector for the evolution chart).

Covers the functional specification:
- with >=1 assessment (chart not empty), a ``.metric-selector`` is rendered
  with 4 buttons, one per metric (peso, massa_magra, gordura_pct, imc);
- the buttons carry the short labels: Peso, Massa magra, % Gordura, IMC;
- the "peso" button is active by default (class "on" + aria-pressed="true"),
  the other three are not (aria-pressed="false", no "on" class);
- the toggle's inline <script> is present in the page;
- with 0 assessments (empty chart state), the ``.metric-selector`` does not
  appear at all.

These are structural checks only: the actual click-to-toggle behaviour is
JS executed client-side and is verified in the browser, not here.

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

METRIC_KEYS = ("peso", "massa_magra", "gordura_pct", "imc")
METRIC_LABELS = {
    "peso": "Peso",
    "massa_magra": "Massa magra",
    "gordura_pct": "% Gordura",
    "imc": "IMC",
}


def _button_slice(html: str, key: str) -> str:
    """Extract the <button ...> tag for a given data-metric-btn key.

    Slices from the button's ``data-metric-btn="key"`` marker back to the
    nearest preceding ``<button`` and forward to the next ``>``, so a test
    can inspect a single button's classes/attributes without parsing the
    whole selector as XML.
    """
    marker = f'data-metric-btn="{key}"'
    marker_pos = html.index(marker)
    tag_start = html.rfind("<button", 0, marker_pos)
    tag_end = html.index(">", marker_pos)
    return html[tag_start : tag_end + 1]


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


def test_selector_and_four_metric_buttons_present_with_assessments(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="70")
        create_avaliacao(aluno["id"], data="2026-02-10", peso="68")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    assert 'class="metric-selector"' in text
    for key in METRIC_KEYS:
        assert f'data-metric-btn="{key}"' in text


def test_metric_button_labels_are_short_portuguese_names(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="70")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    for key, label in METRIC_LABELS.items():
        button = _button_slice(text, key)
        button_end = text.index(button) + len(button)
        next_tag_start = text.index("<", button_end)
        label_slice = text[button_end:next_tag_start]
        assert label in label_slice


def test_peso_button_is_active_by_default_others_are_not(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="70")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    peso_button = _button_slice(text, "peso")
    assert "on" in peso_button.split('class="')[1].split('"')[0].split()
    assert 'aria-pressed="true"' in peso_button

    for key in ("massa_magra", "gordura_pct", "imc"):
        button = _button_slice(text, key)
        classes = button.split('class="')[1].split('"')[0].split()
        assert "on" not in classes
        assert 'aria-pressed="false"' in button


def test_toggle_script_is_present_on_the_page(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")
        create_avaliacao(aluno["id"], data="2026-01-10", peso="70")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    assert "<script>" in text
    assert "querySelectorAll" in text
    assert "data-metric-btn" in text
    assert ".metric-btn" in text


def test_selector_does_not_appear_when_aluno_has_no_assessments(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Maria Silva")

        response = client.get(f"/alunos/{aluno['id']}/avaliacoes")

    assert response.status_code == 200
    text = response.text

    assert "Sem dados para o gráfico." in text
    assert 'class="metric-selector"' not in text
    assert "data-metric-btn" not in text
