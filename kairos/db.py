"""Database engine and session management for the Kairos application.

The database URL comes from :func:`kairos.config.database_url`, which resolves
environment variables at call time. Because of that, the engine cannot be
frozen at import time: this module builds it on demand and caches it keyed by
the URL it was created for. If the URL changes (e.g. a test points
KAIROS_DATA_DIR somewhere else), the next call transparently disposes the old
engine and builds a new one. Tests can also call :func:`dispose_engine` to
force recreation explicitly.

No ORM models live here yet; they will subclass :class:`Base` in future
slices. Schema changes happen only through Alembic migrations.
"""

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from kairos.config import database_url

logger = logging.getLogger(__name__)


def _safe_url(url: str) -> str:
    """Return the URL with any password hidden, safe to log.

    A remote database URL (e.g. Supabase/PostgreSQL) carries a password; it
    must never reach the logs. ``render_as_string(hide_password=True)`` masks
    it as ``***``. Falls back to the driver name if the URL can't be parsed.
    """
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:  # pragma: no cover - defensive, never blocks startup
        return url.split("://", 1)[0] + "://***"


class Base(DeclarativeBase):
    """Declarative base for all Kairos ORM models."""


_engine: Optional[Engine] = None
_engine_url: Optional[str] = None
_session_factory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Return the SQLAlchemy engine for the current database URL.

    The engine is created lazily and cached. If ``database_url()`` returns a
    different URL than the one the cached engine was built for, the cached
    engine is disposed and a new one is created.
    """
    global _engine, _engine_url, _session_factory

    url = database_url()
    if _engine is None or _engine_url != url:
        if _engine is not None:
            logger.info("Database URL changed; disposing cached engine.")
            _engine.dispose()
        _engine = create_engine(url)
        _engine_url = url
        _session_factory = sessionmaker(
            bind=_engine, autoflush=False, expire_on_commit=False
        )
        logger.info("Created database engine for %s", _safe_url(url))
    return _engine


def get_session_factory() -> sessionmaker:
    """Return the session factory bound to the current engine."""
    get_engine()  # ensures the factory matches the current URL
    assert _session_factory is not None
    return _session_factory


def SessionLocal() -> Session:
    """Create a new Session bound to the current engine.

    Named like the conventional SQLAlchemy ``SessionLocal`` factory, but
    implemented as a function so the underlying engine is always resolved
    on demand instead of frozen at import time.
    """
    return get_session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Commits on success, rolls back on error (re-raising the exception),
    and always closes the session.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    """Dispose the cached engine and clear the cache.

    Intended for tests that need a fresh engine (e.g. after changing
    KAIROS_DATA_DIR) or for controlled application shutdown.
    """
    global _engine, _engine_url, _session_factory
    if _engine is not None:
        _engine.dispose()
        logger.info("Disposed database engine for %s", _safe_url(_engine_url))
    _engine = None
    _engine_url = None
    _session_factory = None
