"""F1 — commercial calendar: occurrence math, lead-time scan, settings, dedupe."""

from __future__ import annotations

from datetime import date

from app.services.banners.calendar_service import (
    CalendarService,
    InMemoryCalendarRepository,
    _next_occurrence,
    handle_calendar_scan_job,
)
from app.services.banners.suggestion_service import InMemoryAgentSuggestions, SuggestionService

TEAM = "team-cal"


def _service():
    suggestions = SuggestionService(suggestions=InMemoryAgentSuggestions(), team_id=TEAM)
    return CalendarService(repo=InMemoryCalendarRepository(), suggestions=suggestions, team_id=TEAM), suggestions


def test_next_occurrence_recurring_rolls_to_next_year() -> None:
    event = {"month": 2, "day": 14, "duration_days": 7}
    start, end = _next_occurrence(event, date(2026, 6, 9))
    assert start == date(2027, 2, 14)
    event_soon = {"month": 6, "day": 21, "duration_days": 7}
    start2, _ = _next_occurrence(event_soon, date(2026, 6, 9))
    assert start2 == date(2026, 6, 21)


def test_scan_creates_suggestion_inside_lead_time_with_deadline() -> None:
    svc, suggestions = _service()
    # 2026-06-09: Día del Padre (21 jun) is 12 days out — inside the 14-day lead.
    summary = svc.scan_upcoming(today=date(2026, 6, 9))
    assert "dia-del-padre" in summary["suggestions"]
    pending = suggestions.list()
    padre = next(s for s in pending if "Padre" in s.title)
    assert padre.payload["structured_brief"]["deadline"] == "2026-06-21"
    assert padre.payload["structured_brief"]["urgency"] == "medium"
    # Buen Fin (Nov) is NOT inside the window.
    assert not any("Buen Fin" in s.title for s in pending)


def test_scan_is_idempotent_and_respects_dismissals() -> None:
    svc, suggestions = _service()
    svc.scan_upcoming(today=date(2026, 6, 9))
    first = suggestions.list()[0]
    suggestions.dismiss(str(first.id))
    svc.scan_upcoming(today=date(2026, 6, 10))
    # Not resurrected, not duplicated.
    assert suggestions.list(status="pending") == []


def test_scan_disabled_by_settings() -> None:
    svc, suggestions = _service()
    svc.update_settings({"enabled": False})
    summary = svc.scan_upcoming(today=date(2026, 6, 9))
    assert summary == {"enabled": False, "suggestions": []}
    assert suggestions.list() == []


def test_lead_time_setting_widens_window() -> None:
    svc, suggestions = _service()
    svc.update_settings({"lead_time_days": 70})
    summary = svc.scan_upcoming(today=date(2026, 6, 9))
    assert "regreso-a-clases" in summary["suggestions"]  # 15 ago, ~67 days out


def test_manual_event_with_explicit_dates_is_scanned() -> None:
    svc, suggestions = _service()
    svc.add_manual_event({"slug": "aniversario", "name": "Aniversario de la tienda",
                          "starts_on": "2026-06-15", "duration_days": 3})
    svc.scan_upcoming(today=date(2026, 6, 9))
    assert any("Aniversario" in s.title for s in suggestions.list())


def test_job_handler_runs_without_supabase(monkeypatch) -> None:
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_TEAM_ID"):
        monkeypatch.delenv(var, raising=False)
    summary = handle_calendar_scan_job({"id": "j1", "team_id": "team-demo-cal", "kind": "calendar_scan"})
    assert summary["enabled"] is True
