"""Tests for the development-only auth bypass (KAIROS_DEV_NO_AUTH).

The bypass lets both the coach panel and the student area be reviewed without
logging in. It must be OFF by default (so it never leaks into production) and,
when on, hand each area a synthetic user of the right role.

These exercise the real gate, so they opt out of the suite-wide
"always a coach" fixture with ``@pytest.mark.real_auth``.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.db
from kairos.alunos.service import create_aluno
from kairos.main import app

pytestmark = pytest.mark.real_auth


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def test_gate_still_blocks_when_bypass_is_off(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Default (env unset): the gate still redirects an unauthenticated request.
    monkeypatch.delenv("KAIROS_DEV_NO_AUTH", raising=False)
    with TestClient(app) as client:
        r = client.get("/alunos", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


def test_bypass_opens_coach_panel_without_login(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KAIROS_DEV_NO_AUTH", "1")
    with TestClient(app) as client:
        r = client.get("/alunos")
    assert r.status_code == 200


def test_bypass_opens_student_area_with_dev_aluno(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KAIROS_DEV_NO_AUTH", "1")
    with TestClient(app) as client:
        aluno = create_aluno(name="Bypass Teste")
        monkeypatch.setenv("KAIROS_DEV_ALUNO_ID", str(aluno["id"]))
        r = client.get("/aluno")
    assert r.status_code == 200
    assert "Bypass" in r.text  # greets the dev student by their own name


def test_bypass_student_area_without_dev_aluno_does_not_crash(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No KAIROS_DEV_ALUNO_ID: the student area still renders (generic greeting).
    monkeypatch.setenv("KAIROS_DEV_NO_AUTH", "1")
    monkeypatch.delenv("KAIROS_DEV_ALUNO_ID", raising=False)
    with TestClient(app) as client:
        r = client.get("/aluno")
    assert r.status_code == 200
