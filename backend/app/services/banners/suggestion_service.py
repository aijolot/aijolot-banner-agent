"""SuggestionService — unified proactive agent suggestions (Fase 0).

One model feeds the dashboard panel: calendar events (F1), performance refreshes
(F2) and catalog signals (F3) all become `agent_suggestions` rows with a uniform
pending → accepted | dismissed | expired lifecycle. Producers upsert by
``dedupe_key`` so scans are idempotent; accepting dispatches by kind through
callbacks wired at the API layer (create campaign / start refinement run).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from uuid import uuid4

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.agent_suggestions import AgentSuggestionRepository
from app.schemas.suggestions import (
    AgentSuggestionResponse,
    SuggestionAcceptResponse,
)
from app.services.supabase.client import SupabaseClientFactory

VALID_KINDS = ("calendar_event", "performance_refresh", "catalog_signal")


class SuggestionServiceError(Exception):
    pass


class SuggestionNotFound(SuggestionServiceError):
    def __init__(self, suggestion_id: str) -> None:
        super().__init__(f"suggestion '{suggestion_id}' not found")
        self.suggestion_id = suggestion_id


class SuggestionNotActionable(SuggestionServiceError):
    def __init__(self, suggestion_id: str, status: str) -> None:
        super().__init__(f"suggestion '{suggestion_id}' is '{status}' — only pending suggestions can be acted on")
        self.suggestion_id = suggestion_id
        self.status = status


class SuggestionRepositoryProtocol(Protocol):
    def create(self, *, data: dict[str, Any]) -> dict[str, Any]: ...
    def get(self, *, suggestion_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...
    def get_by_dedupe_key(self, *, team_id: str, dedupe_key: str) -> dict[str, Any] | None: ...
    def list(self, *, team_id: str, status: str | None = None, kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]: ...
    def update(self, *, suggestion_id: str, data: dict[str, Any]) -> dict[str, Any] | None: ...


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryAgentSuggestions:
    """Test/demo double with the same surface as AgentSuggestionRepository."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "status": "pending",
            "rationale": "",
            "payload": {},
            "source_refs": [],
            "campaign_id": None,
            "proposal_id": None,
            "dedupe_key": None,
            "expires_at": None,
            "acted_at": None,
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
            **data,
        }
        self.rows[row["id"]] = row
        return dict(row)

    def get(self, *, suggestion_id: str, team_id: str | None = None) -> dict[str, Any] | None:
        row = self.rows.get(suggestion_id)
        if row and team_id and str(row.get("team_id")) != team_id:
            return None
        return dict(row) if row else None

    def get_by_dedupe_key(self, *, team_id: str, dedupe_key: str) -> dict[str, Any] | None:
        for row in self.rows.values():
            if str(row.get("team_id")) == team_id and row.get("dedupe_key") == dedupe_key:
                return dict(row)
        return None

    def list(self, *, team_id: str, status: str | None = None, kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        rows = [
            dict(r) for r in self.rows.values()
            if str(r.get("team_id")) == team_id
            and (status is None or r.get("status") == status)
            and (kind is None or r.get("kind") == kind)
        ]
        rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        return rows[:limit]

    def update(self, *, suggestion_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        row = self.rows.get(suggestion_id)
        if not row:
            return None
        row.update(data)
        row["updated_at"] = _utc_now_iso()
        return dict(row)


class SuggestionService:
    def __init__(
        self,
        *,
        suggestions: SuggestionRepositoryProtocol,
        team_id: str | None = None,
        # Accept dispatchers, wired by the API layer per kind:
        #   create_campaign(payload) -> campaign_id      (calendar_event, catalog_signal)
        #   start_refinement(suggestion_row) -> run_id   (performance_refresh)
        create_campaign: Callable[[dict[str, Any]], str] | None = None,
        start_refinement: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self.suggestions = suggestions
        self.team_id = team_id
        self.create_campaign = create_campaign
        self.start_refinement = start_refinement

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str, **callbacks: Any) -> "SuggestionService":
        return cls(suggestions=AgentSuggestionRepository(client), team_id=team_id, **callbacks)

    # --- producers (F1/F2/F3 scans) -----------------------------------------

    def upsert_by_dedupe_key(self, *, kind: str, dedupe_key: str, title: str, rationale: str = "",
                             payload: dict[str, Any] | None = None, source_refs: list[dict[str, Any]] | None = None,
                             campaign_id: str | None = None, proposal_id: str | None = None,
                             expires_at: str | None = None) -> dict[str, Any]:
        """Idempotent create: a pending suggestion with the same key is refreshed,
        an acted-on (accepted/dismissed) one is NOT resurrected."""
        if kind not in VALID_KINDS:
            raise SuggestionServiceError(f"invalid suggestion kind '{kind}'")
        team_id = self.team_id or ""
        existing = self.suggestions.get_by_dedupe_key(team_id=team_id, dedupe_key=dedupe_key)
        data = {
            "title": title,
            "rationale": rationale,
            "payload": payload or {},
            "source_refs": source_refs or [],
            "campaign_id": campaign_id,
            "proposal_id": proposal_id,
            "expires_at": expires_at,
        }
        if existing:
            if existing.get("status") != "pending":
                return existing
            return self.suggestions.update(suggestion_id=str(existing["id"]), data=data) or existing
        return self.suggestions.create(data={"team_id": team_id, "kind": kind, "dedupe_key": dedupe_key, **data})

    def expire_stale(self) -> int:
        """Flip pending suggestions whose expires_at passed. Returns count."""
        now = _utc_now_iso()
        expired = 0
        for row in self.suggestions.list(team_id=self.team_id or "", status="pending", limit=200):
            expires_at = str(row.get("expires_at") or "")
            if expires_at and expires_at <= now:
                self.suggestions.update(suggestion_id=str(row["id"]), data={"status": "expired"})
                expired += 1
        return expired

    # --- dashboard consumers --------------------------------------------------

    def list(self, *, status: str | None = "pending", kind: str | None = None, limit: int = 50) -> list[AgentSuggestionResponse]:
        rows = self.suggestions.list(team_id=self.team_id or "", status=status, kind=kind, limit=limit)
        return [AgentSuggestionResponse.model_validate(row) for row in rows]

    def accept(self, suggestion_id: str) -> SuggestionAcceptResponse:
        row = self._get_pending(suggestion_id)
        kind = str(row.get("kind"))
        campaign_id: str | None = None
        run_id: str | None = None
        if kind in ("calendar_event", "catalog_signal"):
            if self.create_campaign is None:
                raise MissingSettingsError(("campaign_service",))
            campaign_id = self.create_campaign(dict(row.get("payload") or {}))
        elif kind == "performance_refresh":
            if self.start_refinement is None:
                raise MissingSettingsError(("generation_run_service",))
            run_id = self.start_refinement(dict(row))
            campaign_id = str(row.get("campaign_id")) if row.get("campaign_id") else None
        updated = self.suggestions.update(
            suggestion_id=suggestion_id,
            data={"status": "accepted", "acted_at": _utc_now_iso(), **({"campaign_id": campaign_id} if campaign_id else {})},
        ) or row
        return SuggestionAcceptResponse(
            suggestion=AgentSuggestionResponse.model_validate(updated),
            campaign_id=campaign_id,
            generation_run_id=run_id,
        )

    def dismiss(self, suggestion_id: str) -> AgentSuggestionResponse:
        self._get_pending(suggestion_id)
        updated = self.suggestions.update(
            suggestion_id=suggestion_id, data={"status": "dismissed", "acted_at": _utc_now_iso()}
        )
        return AgentSuggestionResponse.model_validate(updated)

    def _get_pending(self, suggestion_id: str) -> dict[str, Any]:
        row = self.suggestions.get(suggestion_id=suggestion_id, team_id=self.team_id)
        if not row:
            raise SuggestionNotFound(suggestion_id)
        if str(row.get("status")) != "pending":
            raise SuggestionNotActionable(suggestion_id, str(row.get("status")))
        return row


# --- per-team singleton wiring (same pattern as performance_service) ---------

_team_memory: dict[str, InMemoryAgentSuggestions] = {}


def _memory_for_team(team_id: str) -> InMemoryAgentSuggestions:
    if team_id not in _team_memory:
        _team_memory[team_id] = InMemoryAgentSuggestions()
    return _team_memory[team_id]


def configured_service_for_team(team_id: str, **callbacks: Any) -> SuggestionService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    if not has_supabase_signal:
        return SuggestionService(suggestions=_memory_for_team(team_id), team_id=team_id, **callbacks)
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    client = SupabaseClientFactory(settings).service_role_client()
    return SuggestionService.from_supabase_client(client, team_id=team_id, **callbacks)
