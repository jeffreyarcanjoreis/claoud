"""Tests for the general agenda (Google Calendar, read-only) slice.

Two layers, no network:

- ``kairos.agenda.gcal`` — parsing an ``.ics`` payload and expanding
  recurrences within a window (recurring, all-day, timezone-aware, empty,
  malformed, sorted, "not configured").
- the ``GET /agenda/google`` route and the Agenda navigation — the setup
  state when no calendar is configured, the listing state with a monkeypatched
  fetch, and the friendly error state when the feed can't be read.

Same isolation pattern as the other suites: KAIROS_DATA_DIR points at a temp
dir and the cached engine is disposed on teardown (the app runs migrations on
startup even though this route touches no database).
"""

import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import kairos.agenda.gcal as gcal
import kairos.db
from kairos.agenda.gcal import (
    GcalError,
    GcalNotConfigured,
    fetch_events,
    parse_events,
)
from kairos.main import app


# --------------------------------------------------------------------------- #
# .ics fixtures                                                                #
# --------------------------------------------------------------------------- #

def _ics(body: str) -> bytes:
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//Kairos//EN\r\n"
        f"{body}"
        "END:VCALENDAR\r\n"
    ).encode("utf-8")


def _vevent(**lines: str) -> str:
    inner = "".join(f"{k}:{v}\r\n" for k, v in lines.items())
    return f"BEGIN:VEVENT\r\n{inner}END:VEVENT\r\n"


# --------------------------------------------------------------------------- #
# parse_events — the integration layer                                        #
# --------------------------------------------------------------------------- #

def test_parse_expands_weekly_recurrence_into_occurrences() -> None:
    ics = _ics(
        _vevent(
            **{
                "DTSTART;TZID=America/Sao_Paulo": "20260824T073000",
                "DTEND;TZID=America/Sao_Paulo": "20260824T083000",
                "RRULE": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
                "SUMMARY": "Treino Marcos",
                "UID": "rec@test",
            }
        )
    )
    # Mon 24, Wed 26, Fri 28 fall inside the window.
    events = parse_events(ics, datetime.date(2026, 8, 24), datetime.date(2026, 8, 31))

    treinos = [e for e in events if e.summary == "Treino Marcos"]
    assert len(treinos) == 3
    assert all(not e.all_day for e in treinos)
    assert all(isinstance(e.start, datetime.datetime) for e in treinos)


def test_parse_flags_all_day_event() -> None:
    ics = _ics(
        _vevent(
            **{
                "DTSTART;VALUE=DATE": "20260826",
                "DTEND;VALUE=DATE": "20260827",
                "SUMMARY": "Feriado",
                "UID": "allday@test",
            }
        )
    )
    events = parse_events(ics, datetime.date(2026, 8, 24), datetime.date(2026, 8, 31))

    assert len(events) == 1
    assert events[0].all_day is True
    assert not isinstance(events[0].start, datetime.datetime)
    assert events[0].summary == "Feriado"


def test_parse_reads_summary_and_location() -> None:
    ics = _ics(
        _vevent(
            **{
                "DTSTART;TZID=America/Sao_Paulo": "20260824T090000",
                "DTEND;TZID=America/Sao_Paulo": "20260824T100000",
                "SUMMARY": "Avaliação",
                "LOCATION": "Studio Kairos",
                "UID": "loc@test",
            }
        )
    )
    events = parse_events(ics, datetime.date(2026, 8, 24), datetime.date(2026, 8, 25))

    assert len(events) == 1
    assert events[0].summary == "Avaliação"
    assert events[0].location == "Studio Kairos"


def test_parse_returns_events_sorted_chronologically() -> None:
    ics = _ics(
        _vevent(
            **{
                "DTSTART;TZID=America/Sao_Paulo": "20260825T170000",
                "DTEND;TZID=America/Sao_Paulo": "20260825T180000",
                "SUMMARY": "Tarde",
                "UID": "late@test",
            }
        )
        + _vevent(
            **{
                "DTSTART;TZID=America/Sao_Paulo": "20260824T070000",
                "DTEND;TZID=America/Sao_Paulo": "20260824T080000",
                "SUMMARY": "Manhã",
                "UID": "early@test",
            }
        )
    )
    events = parse_events(ics, datetime.date(2026, 8, 24), datetime.date(2026, 8, 26))

    assert [e.summary for e in events] == ["Manhã", "Tarde"]


def test_parse_empty_calendar_returns_empty_list() -> None:
    events = parse_events(_ics(""), datetime.date(2026, 8, 24), datetime.date(2026, 8, 31))
    assert events == []


def test_parse_malformed_payload_raises_gcal_error() -> None:
    with pytest.raises(GcalError):
        parse_events(b"this is not an ics file", datetime.date(2026, 8, 24), datetime.date(2026, 8, 31))


def test_fetch_events_without_config_raises_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KAIROS_GCAL_ICS_URL", raising=False)
    with pytest.raises(GcalNotConfigured):
        fetch_events(datetime.date(2026, 8, 24), datetime.date(2026, 8, 31))


def test_fetch_events_uses_injected_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIROS_GCAL_ICS_URL", "https://example.com/secret.ics")
    ics = _ics(
        _vevent(
            **{
                "DTSTART;TZID=America/Sao_Paulo": "20260824T073000",
                "DTEND;TZID=America/Sao_Paulo": "20260824T083000",
                "SUMMARY": "Injetado",
                "UID": "inj@test",
            }
        )
    )
    events = fetch_events(
        datetime.date(2026, 8, 24),
        datetime.date(2026, 8, 25),
        fetch=lambda url: ics,
    )
    assert [e.summary for e in events] == ["Injetado"]


# --------------------------------------------------------------------------- #
# GET /agenda/google — the application layer                                   #
# --------------------------------------------------------------------------- #

@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point KAIROS_DATA_DIR at a temp dir and clean up the engine cache."""
    target = tmp_path / "kairos-data"
    monkeypatch.setenv("KAIROS_DATA_DIR", str(target))
    kairos.db.dispose_engine()
    yield target
    kairos.db.dispose_engine()


def test_google_agenda_without_config_shows_setup_state(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KAIROS_GCAL_ICS_URL", raising=False)
    with TestClient(app) as client:
        response = client.get("/agenda/google")

    assert response.status_code == 200
    assert "Endereço secreto" in response.text
    assert "KAIROS_GCAL_ICS_URL" in response.text


def test_google_agenda_lists_events_grouped_by_day(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hoje = datetime.date.today()
    amanha = hoje + datetime.timedelta(days=1)

    def _fmt(d: datetime.date, hhmm: str) -> str:
        return f"{d.strftime('%Y%m%d')}T{hhmm}00"

    ics = _ics(
        _vevent(
            **{
                "DTSTART;TZID=America/Sao_Paulo": _fmt(hoje, "0730"),
                "DTEND;TZID=America/Sao_Paulo": _fmt(hoje, "0830"),
                "SUMMARY": "Treino Manhã",
                "LOCATION": "Studio Kairos",
                "UID": "a@test",
            }
        )
        + _vevent(
            **{
                "DTSTART;TZID=America/Sao_Paulo": _fmt(amanha, "1800"),
                "DTEND;TZID=America/Sao_Paulo": _fmt(amanha, "1900"),
                "SUMMARY": "Treino Tarde",
                "UID": "b@test",
            }
        )
    )

    monkeypatch.setenv("KAIROS_GCAL_ICS_URL", "https://example.com/secret.ics")
    monkeypatch.setattr(gcal, "_fetch", lambda url: ics)

    with TestClient(app) as client:
        response = client.get("/agenda/google")

    assert response.status_code == 200
    text = response.text
    assert "Treino Manhã" in text
    assert "Treino Tarde" in text
    assert "07:30" in text
    assert "18:00" in text
    assert "Studio Kairos" in text
    # earliest day/event appears before the later one
    assert text.index("Treino Manhã") < text.index("Treino Tarde")


def test_google_agenda_empty_feed_shows_empty_state(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KAIROS_GCAL_ICS_URL", "https://example.com/secret.ics")
    monkeypatch.setattr(gcal, "_fetch", lambda url: _ics(""))

    with TestClient(app) as client:
        response = client.get("/agenda/google")

    assert response.status_code == 200
    assert "Nenhum treino no Google Calendar" in response.text


def test_google_agenda_fetch_error_shows_error_state(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(url: str) -> bytes:
        raise GcalError("falhou")

    monkeypatch.setenv("KAIROS_GCAL_ICS_URL", "https://example.com/secret.ics")
    monkeypatch.setattr(gcal, "_fetch", _boom)

    with TestClient(app) as client:
        response = client.get("/agenda/google")

    assert response.status_code == 502
    assert "Não foi possível ler o calendário" in response.text


def test_agenda_nav_tab_and_subnav_present(data_dir: Path) -> None:
    with TestClient(app) as client:
        response = client.get("/agenda")

    assert response.status_code == 200
    text = response.text
    # top-level "Agenda" tab
    assert '<a class="tab' in text and 'href="/agenda">Agenda</a>' in text
    # sub-nav links to both views
    assert 'href="/agenda">Sessões de hoje</a>' in text
    assert 'href="/agenda/google">Google Calendar</a>' in text
