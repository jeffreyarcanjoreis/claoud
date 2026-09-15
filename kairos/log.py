"""Logging setup for the Kairos application."""

import logging
import sys

from kairos.config import log_level

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging() -> None:
    """Configure root logging to stderr.

    Idempotent: calling it multiple times does not add duplicate handlers.
    The level is re-applied on every call so tests can change
    KAIROS_LOG_LEVEL and re-run setup.
    """
    root = logging.getLogger()
    root.setLevel(log_level())

    already_configured = any(
        getattr(handler, "_kairos_handler", False) for handler in root.handlers
    )
    if already_configured:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler._kairos_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
