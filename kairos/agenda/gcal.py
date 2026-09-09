"""Integration layer: a read-only view of the coach's Google Calendar.

The coach's Google Calendar exposes a private *secret address in iCal format*
(a ``.ics`` URL). This module fetches that feed over HTTP and turns it into a
list of normalized events, expanding recurring events (e.g. a weekly training)
into their concrete occurrences within a date window.

This is a pure read/interpretation layer (architecture: integration layer):
no database, no business rules, no writes to Google. The secret URL is a
credential -- it comes from :func:`kairos.config.gcal_ics_url` and is never
logged. Fetch failures and malformed feeds are converted into a typed
:class:`GcalError` so the application layer can show a friendly state instead
of crashing (and never invents events -- rule 6).

Google Calendar sync in the *write* direction (pushing our own sessions to the
calendar) is a separate, future slice; nothing here writes anything.
"""

from __future__ import annotations

import datetime as _dt
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, List, Optional

import icalendar
import recurring_ical_events

from kairos import config

# A local single-user tool talking to Google: keep the request bounded so a
# slow or unreachable feed never hangs the panel.
_FETCH_TIMEOUT_S = 10

# webcal:// is how calendar apps hand out the same feed; it is https under the
# hood. Anything else (file://, ftp://, ...) is refused.
_ALLOWED_SCHEMES = ("http", "https", "webcal")


class GcalError(Exception):
    """The calendar feed could not be fetched or understood."""


class GcalNotConfigured(GcalError):
    """No iCal secret URL is configured (``KAIROS_GCAL_ICS_URL`` unset)."""


@dataclass(frozen=True)
class GcalEvent:
    """One concrete calendar occurrence within the requested window.

    ``start``/``end`` are :class:`datetime.date` for all-day events and
    (timezone-aware) :class:`datetime.datetime` for timed ones, exactly as the
    feed carries them; the application layer formats them for display.
    """

    summary: str
    start: object
    end: object
    all_day: bool
    location: Optional[str]
    description: Optional[str]


def _normalize_url(url: str) -> str:
    """Validate the scheme and rewrite ``webcal://`` to ``https://``."""
    u = url.strip()
    scheme = u.split("://", 1)[0].lower() if "://" in u else ""
    if scheme not in _ALLOWED_SCHEMES:
        raise GcalError("Endereço de calendário inválido.")
    if scheme == "webcal":
        u = "https://" + u.split("://", 1)[1]
    return u


def _fetch(url: str) -> bytes:
    """Fetch the raw ``.ics`` bytes; raise :class:`GcalError` on any failure."""
    safe = _normalize_url(url)
    try:
        request = urllib.request.Request(safe, headers={"User-Agent": "Kairos/0.1"})
        with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT_S) as response:
            return response.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # The URL is a credential: do not put it in the message/log.
        raise GcalError("Não foi possível ler o calendário agora.") from exc


def _text(value: object) -> Optional[str]:
    """Coerce an optional iCal field to a trimmed string or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sort_key(event: GcalEvent):
    """Chronological key that safely mixes all-day and timezone-aware times."""
    start = event.start
    if isinstance(start, _dt.datetime):
        if start.tzinfo is not None:
            return start.astimezone(_dt.timezone.utc)
        return start.replace(tzinfo=_dt.timezone.utc)
    return _dt.datetime.combine(start, _dt.time(0, 0), tzinfo=_dt.timezone.utc)


def parse_events(
    ics_bytes: bytes, start: _dt.date, end: _dt.date
) -> List[GcalEvent]:
    """Parse an ``.ics`` payload and expand recurrences within ``[start, end]``.

    Returns the occurrences sorted chronologically. Raises :class:`GcalError`
    when the payload is not a calendar we can read.
    """
    try:
        calendar = icalendar.Calendar.from_ical(ics_bytes)
        occurrences = recurring_ical_events.of(calendar).between(start, end)
    except GcalError:
        raise
    except Exception as exc:  # icalendar surfaces many parse-error types
        raise GcalError("Calendário em formato inesperado.") from exc

    events: List[GcalEvent] = []
    for comp in occurrences:
        dtstart = comp.get("DTSTART")
        if dtstart is None:
            continue
        start_value = dtstart.dt
        dtend = comp.get("DTEND")
        end_value = dtend.dt if dtend is not None else None
        events.append(
            GcalEvent(
                summary=_text(comp.get("SUMMARY")) or "(sem título)",
                start=start_value,
                end=end_value,
                all_day=not isinstance(start_value, _dt.datetime),
                location=_text(comp.get("LOCATION")),
                description=_text(comp.get("DESCRIPTION")),
            )
        )

    events.sort(key=_sort_key)
    return events


def fetch_events(
    start: _dt.date,
    end: _dt.date,
    *,
    fetch: Optional[Callable[[str], bytes]] = None,
) -> List[GcalEvent]:
    """Fetch and parse the configured calendar for the ``[start, end]`` window.

    Raises :class:`GcalNotConfigured` when no URL is set, and :class:`GcalError`
    on any fetch/parse failure. ``fetch`` is injectable so tests never touch the
    network.
    """
    url = config.gcal_ics_url()
    if not url:
        raise GcalNotConfigured("Google Calendar não configurado.")
    fetcher = fetch or _fetch
    return parse_events(fetcher(url), start, end)
