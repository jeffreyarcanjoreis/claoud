"""Shared test setup.

Every test isolates the database via KAIROS_DATA_DIR (see each test file's
own ``data_dir`` fixture). KAIROS_DATABASE_URL, if present in the local
.env (pointing at Supabase/PostgreSQL), must never leak into a test run —
otherwise tests would hit the real remote database instead of an isolated
SQLite temp file.
"""

import pytest


@pytest.fixture(autouse=True)
def _no_remote_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force every test onto SQLite, regardless of KAIROS_DATABASE_URL."""
    monkeypatch.delenv("KAIROS_DATABASE_URL", raising=False)
