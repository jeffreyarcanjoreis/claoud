"""Tests for issue 04 (coach reads the aluno's self-recognized level --
read-only) -- ``GET /alunos/{aluno_id}/nivel``.

Covers the functional specification:

- the coach's "Nível" sub-tab shows the aluno's current self-recognized
  level (most recent :func:`kairos.nivel.service.reconhecer` call) and the
  full history, including any free-text ``nota``;
- when the aluno has never self-recognized a level, the page shows
  "Sem registro -- aguardando o aluno se reconhecer." instead;
- a non-existent aluno returns 404;
- the page is read-only: the coach never sets the aluno's level here (no
  form/button inside the "Nível" sub-tab content, unlike the aluno-actions
  forms -- arquivar/reativar -- that live in the shared ficha header).

Isolation: KAIROS_DATA_DIR points at a temp dir and the cached engine is
disposed on setup/teardown (same pattern as tests/test_checkin.py). The
suite-wide ``_auto_login_as_coach`` fixture (see tests/conftest.py) already
auto-authenticates every request as a coach, so no login flow is needed
here.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app
from kairos.nivel.service import reconhecer


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()  # drop any engine cached for a previous URL
    yield target
    kairos.db.dispose_engine()  # release the SQLite file handle (Windows)


# ---------------------------------------------------------------------------
# Marker used to isolate the "Nível" sub-tab content from the shared ficha
# header (which legitimately contains arquivar/reativar forms).
# ---------------------------------------------------------------------------
_CONTENT_MARKER = "Nível reconhecido pelo aluno"


def _nivel_content(html: str) -> str:
    """Return the portion of the rendered page starting at the "Nível"
    sub-tab content, excluding the shared ficha header (which has its own
    unrelated arquivar/reativar forms)."""
    assert _CONTENT_MARKER in html
    return html.split(_CONTENT_MARKER, 1)[1]


def test_coach_sees_current_level_and_history_with_note(data_dir: Path) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        reconhecer(aluno["id"], nivel="construcao")
        reconhecer(aluno["id"], nivel="dominio", nota="cresci")

        response = client.get(f"/alunos/{aluno['id']}/nivel")

    assert response.status_code == 200
    assert "III · Domínio" in response.text
    assert "cresci" in response.text
    # History includes both recognitions.
    assert "II · Construção" in response.text


def test_coach_sees_awaiting_message_when_aluno_never_recognized_a_level(
    data_dir: Path,
) -> None:
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")

        response = client.get(f"/alunos/{aluno['id']}/nivel")

    assert response.status_code == 200
    assert "Sem registro" in response.text


def test_coach_nivel_for_nonexistent_aluno_returns_404(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/alunos/999999/nivel")

    assert response.status_code == 404


def test_coach_nivel_tab_is_read_only(data_dir: Path) -> None:
    """The "Nível" sub-tab content has no form/button of its own: the coach
    only observes, and never sets, the aluno's self-recognized level.

    The shared ficha header does contain arquivar/reativar forms, so the
    check is scoped to the content that follows the "Nível" sub-tab's own
    marker (see ``_nivel_content``), not the whole response body.
    """
    with TestClient(app) as client:
        aluno = create_aluno(name="Marcos Vieira")
        reconhecer(aluno["id"], nivel="fundacao")

        response = client.get(f"/alunos/{aluno['id']}/nivel")

    assert response.status_code == 200
    content = _nivel_content(response.text)
    assert "<form" not in content
    assert "<button" not in content
