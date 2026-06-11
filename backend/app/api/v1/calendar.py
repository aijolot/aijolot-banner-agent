"""/api/v1 commercial calendar (F1).

GET  /calendar/events    — global seed + team events
POST /calendar/events    — add a manual team event
GET  /calendar/settings  — lead time / auto-concept / enabled
PUT  /calendar/settings
POST /calendar/infer     — LLM niche-date inference (no-op without a key)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.core.auth import require_user_context
from app.services.banners.calendar_service import CalendarService, configured_calendar_service_for_team
from app.services.banners.async_run import run_coro

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _service(request: Request) -> CalendarService:
    context = require_user_context(request)
    return configured_calendar_service_for_team(context.team_id)


@router.get("/events")
def list_events(request: Request) -> dict[str, Any]:
    return {"events": _service(request).list_events()}


@router.post("/events")
def add_event(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    return {"event": _service(request).add_manual_event(dict(payload or {}))}


@router.get("/settings")
def get_settings(request: Request) -> dict[str, Any]:
    return _service(request).get_settings()


@router.put("/settings")
def update_settings(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    return _service(request).update_settings(dict(payload or {}))


@router.post("/scan")
def scan_now(request: Request) -> dict[str, Any]:
    """Run the calendar scan for this team NOW (UI trigger — same logic the
    daily calendar_scan job executes via pg_cron + poller)."""
    return _service(request).scan_upcoming()


@router.post("/infer")
def infer_niche_events(request: Request) -> dict[str, Any]:
    service = _service(request)
    events = run_coro(service.infer_niche_events())
    return {"inferred": events}
