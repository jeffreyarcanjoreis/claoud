"""Shared test setup.

Every test isolates the database via KAIROS_DATA_DIR (see each test file's
own ``data_dir`` fixture). KAIROS_DATABASE_URL, if present in the local
.env (pointing at Supabase/PostgreSQL), must never leak into a test run —
otherwise tests would hit the real remote database instead of an isolated
SQLite temp file.

Issue 26 (Fase 1) added ``AuthGateMiddleware``, which redirects any request
to a non-public path to ``/login`` unless a coach session exists. Every test
written before that gate exercises the panel directly (no login flow), so by
default every test is auto-authenticated as a coach (see
``_auto_login_as_coach`` below). Tests that exercise the real auth gate/flow
opt out with ``@pytest.mark.real_auth``.
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers used across the suite."""
    config.addinivalue_line(
        "markers",
        "real_auth: exercise the real AuthGateMiddleware/login flow "
        "instead of the auto-login-as-coach fixture.",
    )


@pytest.fixture(autouse=True)
def _no_remote_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force every test onto SQLite, regardless of KAIROS_DATABASE_URL."""
    monkeypatch.delenv("KAIROS_DATABASE_URL", raising=False)


@pytest.fixture(autouse=True)
def _auto_login_as_coach(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bypass ``AuthGateMiddleware`` for every test except ``real_auth`` ones.

    Patches ``kairos.auth.middleware.current_user`` — the single function the
    gate calls to decide whether a request carries a coach session — so every
    pre-existing test keeps hitting the panel directly, without a login flow.
    Tests marked ``@pytest.mark.real_auth`` (tests/test_auth.py) opt out and
    exercise the real gate/session instead.
    """
    if request.node.get_closest_marker("real_auth") is not None:
        return

    monkeypatch.setattr(
        "kairos.auth.middleware.current_user",
        lambda request: {
            "user_id": "test-coach",
            "email": "coach@test",
            "papel": "coach",
        },
    )
