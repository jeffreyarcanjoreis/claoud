"""Application settings resolved from environment variables.

Every setting is exposed as a function (not a module-level constant) so that
values are resolved at call time. Tests can change environment variables after
this module has been imported and still get the updated values.
"""

import os
from pathlib import Path
from typing import Optional

# Project root: the directory that contains the `kairos` package.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load a local ``.env`` (project root) into the environment, if present.

    Minimal parser (no dependency): each ``KEY=VALUE`` line is applied with
    ``setdefault``, so a real environment variable always wins over the file
    and tests that set env vars stay in control. Lines that are blank or start
    with ``#`` are ignored; surrounding quotes on the value are stripped. The
    ``.env`` file is git-ignored and holds local secrets like
    ``KAIROS_GCAL_ICS_URL``. Never logged.
    """
    env_file = _PROJECT_ROOT / ".env"
    try:
        text = env_file.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


def data_dir() -> Path:
    """Directory where application data lives (env: KAIROS_DATA_DIR)."""
    raw = os.environ.get("KAIROS_DATA_DIR")
    if raw:
        return Path(raw)
    return _PROJECT_ROOT / "data"


def db_path() -> Path:
    """Path to the SQLite database file."""
    return data_dir() / "kairos.db"


def backups_dir() -> Path:
    """Directory where database backups are stored."""
    return data_dir() / "backups"


def fotos_dir() -> Path:
    """Directory where uploaded student photos are stored."""
    return data_dir() / "fotos"


def database_url() -> str:
    """SQLAlchemy database URL.

    Reads ``KAIROS_DATABASE_URL`` when set (e.g. a Supabase/PostgreSQL
    connection string) and falls back to the local SQLite file otherwise
    (architecture rule 4: switching database must require only
    configuration). A bare ``postgres://`` or ``postgresql://`` URL, as
    Supabase hands out, is normalized to the pg8000 driver (pure Python,
    no native extension — avoids DLL-loading issues under restrictive
    Windows application-control policies).
    """
    raw = os.environ.get("KAIROS_DATABASE_URL")
    if raw:
        raw = raw.strip()
        for prefix in ("postgres://", "postgresql://"):
            if raw.startswith(prefix) and not raw.startswith("postgresql+"):
                return "postgresql+pg8000://" + raw[len(prefix):]
        return raw
    return f"sqlite:///{db_path().resolve().as_posix()}"


def log_level() -> str:
    """Logging level name (env: KAIROS_LOG_LEVEL, default INFO)."""
    return os.environ.get("KAIROS_LOG_LEVEL", "INFO").upper()


def gcal_ics_url() -> Optional[str]:
    """Private iCal (.ics) secret address of the coach's Google Calendar.

    Read-only integration: the app fetches this feed to *show* the calendar in
    the panel, never to write to it. It is a credential (anyone with the link
    can read the calendar), so it lives only in the environment
    (``KAIROS_GCAL_ICS_URL``) and is never logged. Returns ``None`` when unset,
    so the panel can show a setup state instead of inventing data (rule 6).
    """
    raw = os.environ.get("KAIROS_GCAL_ICS_URL")
    if raw and raw.strip():
        return raw.strip()
    return None
