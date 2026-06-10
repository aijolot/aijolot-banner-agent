"""CalendarService (F1) — proactive commercial calendar.

Knows the commercial dates (MX-first + global seed, recurring annually) PLUS
team-scoped niche events inferred by the LLM from the brand/catalog context.
``scan_upcoming`` (the ``calendar_scan`` agent job) turns events inside the
team's lead time into agent_suggestions with a prefilled brief — idempotent per
(slug, year), never resurrecting dismissed suggestions.

Deterministic-first: the seed calendar works with zero LLM/Supabase; niche
inference is Gemini-optional and returns [] silently without a key.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from app.agents.tools import gemini_text

EST_INFER_USD = 0.002

# In-code mirror of the migration seed so demo/in-memory mode behaves the same.
SEED_EVENTS: list[dict[str, Any]] = [
    {"slug": "dia-de-reyes", "name": "Día de Reyes", "country": "MX", "month": 1, "day": 6, "duration_days": 3,
     "source": "seed", "relevance_note": "Regalos de Reyes — última campaña de la temporada navideña."},
    {"slug": "san-valentin", "name": "San Valentín", "country": "GLOBAL", "month": 2, "day": 14, "duration_days": 7,
     "source": "seed", "relevance_note": "Regalos de pareja y autorregalo."},
    {"slug": "dia-de-las-madres", "name": "Día de las Madres (MX)", "country": "MX", "month": 5, "day": 10, "duration_days": 7,
     "source": "seed", "relevance_note": "Una de las fechas de mayor venta del retail mexicano."},
    {"slug": "hot-sale", "name": "Hot Sale MX", "country": "MX", "month": 5, "day": 26, "duration_days": 6,
     "source": "seed", "relevance_note": "El evento de ecommerce más grande de México."},
    {"slug": "dia-del-padre", "name": "Día del Padre", "country": "MX", "month": 6, "day": 21, "duration_days": 7,
     "source": "seed", "relevance_note": "Tercer domingo de junio (aprox)."},
    {"slug": "regreso-a-clases", "name": "Regreso a clases", "country": "MX", "month": 8, "day": 15, "duration_days": 21,
     "source": "seed", "relevance_note": "Útiles, ropa, tecnología y accesorios."},
    {"slug": "el-buen-fin", "name": "El Buen Fin", "country": "MX", "month": 11, "day": 13, "duration_days": 5,
     "source": "seed", "relevance_note": "El fin de semana más barato del año."},
    {"slug": "black-friday-cyber", "name": "Black Friday + Cyber Monday", "country": "GLOBAL", "month": 11, "day": 27, "duration_days": 5,
     "source": "seed", "relevance_note": "BFCM — pico global de descuentos."},
    {"slug": "navidad", "name": "Navidad", "country": "GLOBAL", "month": 12, "day": 24, "duration_days": 8,
     "source": "seed", "relevance_note": "Campañas de regalos navideños y envío garantizado."},
]

DEFAULT_LEAD_TIME_DAYS = 14


class NicheEvent(BaseModel):
    slug: str = ""
    name: str = ""
    starts_on: str = Field(default="", description="ISO date YYYY-MM-DD")
    duration_days: int = 7
    relevance_note: str = ""


class NicheEventInference(BaseModel):
    events: list[NicheEvent] = Field(default_factory=list)


class CalendarRepositoryProtocol(Protocol):
    def list_events(self, *, team_id: str) -> list[dict[str, Any]]: ...
    def upsert_event(self, *, team_id: str | None, data: dict[str, Any]) -> dict[str, Any]: ...
    def get_settings(self, *, team_id: str) -> dict[str, Any] | None: ...
    def upsert_settings(self, *, team_id: str, data: dict[str, Any]) -> dict[str, Any]: ...


class InMemoryCalendarRepository:
    """Global seed + team events + settings, in memory (tests/demo)."""

    def __init__(self) -> None:
        self.events: dict[tuple[str, str], dict[str, Any]] = {}
        self.settings: dict[str, dict[str, Any]] = {}
        for event in SEED_EVENTS:
            self.events[("global", event["slug"])] = {"id": str(uuid4()), "team_id": None, **event}

    def list_events(self, *, team_id: str) -> list[dict[str, Any]]:
        return [dict(r) for key, r in self.events.items() if key[0] in ("global", team_id)]

    def upsert_event(self, *, team_id: str | None, data: dict[str, Any]) -> dict[str, Any]:
        key = (team_id or "global", str(data.get("slug")))
        row = self.events.get(key) or {"id": str(uuid4()), "team_id": team_id}
        row.update(data)
        self.events[key] = row
        return dict(row)

    def get_settings(self, *, team_id: str) -> dict[str, Any] | None:
        return dict(self.settings[team_id]) if team_id in self.settings else None

    def upsert_settings(self, *, team_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = self.settings.get(team_id) or {"team_id": team_id, "lead_time_days": DEFAULT_LEAD_TIME_DAYS,
                                             "auto_concept": False, "enabled": True}
        row.update(data)
        self.settings[team_id] = row
        return dict(row)


class SupabaseCalendarRepository:
    def __init__(self, client: Any) -> None:
        self.client = client

    def list_events(self, *, team_id: str) -> list[dict[str, Any]]:
        from app.db.repositories._supabase import execute_data

        out = execute_data(
            self.client.table("commercial_calendar_events")
            .select("id,team_id,slug,name,country,month,day,duration_days,starts_on,ends_on,source,relevance_note")
            .or_(f"team_id.is.null,team_id.eq.{team_id}")
            .limit(500)
        )
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def upsert_event(self, *, team_id: str | None, data: dict[str, Any]) -> dict[str, Any]:
        from app.db.repositories._supabase import execute_data

        payload = {"team_id": team_id, **{k: v for k, v in data.items() if k in (
            "slug", "name", "country", "month", "day", "duration_days", "starts_on", "ends_on", "source", "relevance_note")}}
        out = execute_data(self.client.table("commercial_calendar_events").upsert(payload).select("*"))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def get_settings(self, *, team_id: str) -> dict[str, Any] | None:
        from app.db.repositories._supabase import execute_data

        out = execute_data(
            self.client.table("team_calendar_settings").select("team_id,lead_time_days,auto_concept,enabled")
            .eq("team_id", team_id).limit(1)
        )
        rows = out if isinstance(out, list) else ([out] if out else [])
        return dict(rows[0]) if rows else None

    def upsert_settings(self, *, team_id: str, data: dict[str, Any]) -> dict[str, Any]:
        from app.db.repositories._supabase import execute_data

        payload = {"team_id": team_id, **{k: v for k, v in data.items() if k in ("lead_time_days", "auto_concept", "enabled")}}
        out = execute_data(self.client.table("team_calendar_settings").upsert(payload, on_conflict="team_id").select("*"))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})


def _next_occurrence(event: dict[str, Any], today: date) -> tuple[date, date] | None:
    """(starts_on, ends_on) of the event's next occurrence on/after today's window."""
    starts_on = event.get("starts_on")
    if starts_on:
        try:
            start = date.fromisoformat(str(starts_on))
        except ValueError:
            return None
        ends_raw = event.get("ends_on")
        try:
            end = date.fromisoformat(str(ends_raw)) if ends_raw else start + timedelta(days=int(event.get("duration_days") or 7))
        except ValueError:
            end = start + timedelta(days=7)
        return (start, end) if end >= today else None
    month, day = event.get("month"), event.get("day")
    if not month or not day:
        return None
    duration = int(event.get("duration_days") or 7)
    for year in (today.year, today.year + 1):
        try:
            start = date(year, int(month), int(day))
        except ValueError:
            continue
        end = start + timedelta(days=duration)
        if end >= today:
            return start, end
    return None


class CalendarService:
    def __init__(self, *, repo: CalendarRepositoryProtocol, suggestions: Any, team_id: str,
                 settings: Any = None, cost_guard: Any = None) -> None:
        self.repo = repo
        self.suggestions = suggestions
        self.team_id = team_id
        self.settings = settings
        self.cost_guard = cost_guard

    # --- settings -------------------------------------------------------------

    def get_settings(self) -> dict[str, Any]:
        return self.repo.get_settings(team_id=self.team_id) or {
            "team_id": self.team_id, "lead_time_days": DEFAULT_LEAD_TIME_DAYS, "auto_concept": False, "enabled": True,
        }

    def update_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        if "lead_time_days" in data:
            try:
                clean["lead_time_days"] = max(1, min(90, int(data["lead_time_days"])))
            except (TypeError, ValueError):
                pass
        for key in ("auto_concept", "enabled"):
            if key in data:
                clean[key] = bool(data[key])
        return self.repo.upsert_settings(team_id=self.team_id, data=clean)

    # --- events ---------------------------------------------------------------

    def list_events(self) -> list[dict[str, Any]]:
        return self.repo.list_events(team_id=self.team_id)

    def add_manual_event(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.repo.upsert_event(team_id=self.team_id, data={**data, "source": "manual"})

    async def infer_niche_events(self, *, brand_context: Any = None, catalog_sample: list[str] | None = None) -> list[dict[str, Any]]:
        """LLM: niche dates relevant to THIS store (e.g. back-to-school for a
        stationery store). Without a key (or on any failure) returns [] — the
        seed calendar alone keeps the feature working. Idempotent per slug."""
        if self.settings is None or not getattr(self.settings, "has_google_api_key", lambda: False)():
            return []
        try:
            from app.services.gemini.cost_guard import get_default_cost_guard

            guard = self.cost_guard or get_default_cost_guard(self.settings)
            if not guard.check_and_reserve(EST_INFER_USD).allowed:
                return []
            notes = str(getattr(brand_context, "notes", "") or "")[:300]
            name = str(getattr(brand_context, "name", "") or "la tienda")
            products = ", ".join((catalog_sample or [])[:10])
            today = datetime.now(timezone.utc).date().isoformat()
            prompt = (
                "You are a retail marketing planner for a Mexican ecommerce store. Infer up to 4 NICHE commercial "
                "dates relevant to THIS store's vertical that are NOT generic retail dates (NOT Buen Fin, BFCM, "
                "Navidad, Reyes, San Valentín, Día de las Madres/Padre, Hot Sale, regreso a clases).\n"
                f"Store: {name}\nBrand notes: {notes}\nSample products: {products or 'unknown'}\nToday: {today}\n"
                "Return JSON {events:[{slug, name, starts_on (next occurrence, ISO date), duration_days, "
                "relevance_note (one sentence in Spanish)}]}. Only include dates within the next 12 months."
            )
            result = await gemini_text.generate(prompt, model=gemini_text.FLASH_MODEL, structured=NicheEventInference)
        except gemini_text.GeminiUnavailable:
            return []
        except Exception:  # noqa: BLE001 — inference is best-effort
            return []
        if not isinstance(result, NicheEventInference):
            return []
        stored: list[dict[str, Any]] = []
        for event in result.events[:4]:
            slug = (event.slug or event.name).strip().lower().replace(" ", "-")[:60]
            if not slug or not event.starts_on:
                continue
            try:
                date.fromisoformat(event.starts_on)
            except ValueError:
                continue
            stored.append(self.repo.upsert_event(team_id=self.team_id, data={
                "slug": slug, "name": event.name or slug, "country": "MX",
                "starts_on": event.starts_on, "duration_days": max(1, min(45, int(event.duration_days or 7))),
                "source": "niche_inferred", "relevance_note": (event.relevance_note or "")[:280],
            }))
        return stored

    # --- proactive scan (calendar_scan agent job) ------------------------------

    def scan_upcoming(self, *, today: date | None = None) -> dict[str, Any]:
        settings = self.get_settings()
        if not settings.get("enabled", True):
            return {"enabled": False, "suggestions": []}
        lead = int(settings.get("lead_time_days") or DEFAULT_LEAD_TIME_DAYS)
        today = today or datetime.now(timezone.utc).date()
        horizon = today + timedelta(days=lead)
        created: list[str] = []
        suggestion_rows: list[dict[str, Any]] = []
        for event in self.list_events():
            occurrence = _next_occurrence(event, today)
            if occurrence is None:
                continue
            start, end = occurrence
            if start > horizon:
                continue
            days_left = (start - today).days
            urgency = "high" if days_left <= 7 else "medium"
            name = str(event.get("name") or event.get("slug"))
            note = str(event.get("relevance_note") or "")
            row = self.suggestions.upsert_by_dedupe_key(
                kind="calendar_event",
                dedupe_key=f"calendar:{event.get('slug')}:{start.year}",
                title=f"Prepara tu campaña de {name}",
                rationale=(
                    (f"Empieza en {days_left} días ({start.isoformat()})." if days_left > 0 else f"¡Es hoy! ({start.isoformat()}).")
                    + (f" {note}" if note else "")
                ),
                payload={
                    "title": f"Campaña {name} {start.year}",
                    "structured_brief": {
                        "goal": f"Campaña de {name}",
                        "urgency": urgency,
                        "deadline": start.isoformat(),
                    },
                },
                source_refs=[{"type": "calendar_event", "id": str(event.get("id") or ""), "title": name}],
                expires_at=datetime(end.year, end.month, end.day, tzinfo=timezone.utc).isoformat(),
            )
            created.append(str(event.get("slug")))
            suggestion_rows.append(
                {
                    "id": str(row.get("id")), "slug": str(event.get("slug")), "title": str(row.get("title") or ""),
                    "status": str(row.get("status") or "pending"), "starts_on": start.isoformat(),
                }
            )
        return {"enabled": True, "lead_time_days": lead, "suggestions": created, "suggestion_rows": suggestion_rows}


# --- agent-job handler (kind='calendar_scan') ----------------------------------


def handle_calendar_scan_job(job: dict[str, Any]) -> dict[str, Any]:
    from app.core.settings import Settings
    from app.services.banners.suggestion_service import configured_service_for_team
    from app.services.supabase.client import SupabaseClientFactory

    team_id = str(job.get("team_id") or "")
    settings = Settings.from_env()
    if settings.supabase_url and settings.supabase_service_role_key:
        client = SupabaseClientFactory(settings).service_role_client()
        repo: CalendarRepositoryProtocol = SupabaseCalendarRepository(client)
    else:
        repo = _memory_repo_for_team(team_id)
    suggestions = configured_service_for_team(team_id)
    service = CalendarService(repo=repo, suggestions=suggestions, team_id=team_id, settings=settings)
    return service.scan_upcoming()


_team_calendar_memory: dict[str, InMemoryCalendarRepository] = {}


def _memory_repo_for_team(team_id: str) -> InMemoryCalendarRepository:
    if team_id not in _team_calendar_memory:
        _team_calendar_memory[team_id] = InMemoryCalendarRepository()
    return _team_calendar_memory[team_id]


def configured_calendar_service_for_team(team_id: str) -> CalendarService:
    from app.core.settings import Settings
    from app.services.banners.suggestion_service import configured_service_for_team
    from app.services.supabase.client import SupabaseClientFactory

    settings = Settings.from_env()
    suggestions = configured_service_for_team(team_id)
    if settings.supabase_url and settings.supabase_service_role_key:
        client = SupabaseClientFactory(settings).service_role_client()
        return CalendarService(repo=SupabaseCalendarRepository(client), suggestions=suggestions, team_id=team_id, settings=settings)
    return CalendarService(repo=_memory_repo_for_team(team_id), suggestions=suggestions, team_id=team_id, settings=settings)
