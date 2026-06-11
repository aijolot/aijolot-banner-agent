"""Schemas for proactive agent suggestions (Fase 0 — dashboard panel)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SuggestionKind = Literal["calendar_event", "performance_refresh", "catalog_signal"]
SuggestionStatus = Literal["pending", "accepted", "dismissed", "expired"]


class AgentSuggestionResponse(BaseModel):
    id: str
    team_id: str | None = None
    kind: SuggestionKind
    status: SuggestionStatus
    title: str
    rationale: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    campaign_id: str | None = None
    proposal_id: str | None = None
    dedupe_key: str | None = None
    expires_at: str | None = None
    acted_at: str | None = None
    created_at: str | None = None


class SuggestionListResponse(BaseModel):
    suggestions: list[AgentSuggestionResponse] = Field(default_factory=list)


class SuggestionAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_by: str | None = None


class SuggestionAcceptResponse(BaseModel):
    suggestion: AgentSuggestionResponse
    # What the accept produced, by kind: a new campaign (calendar/catalog) or a
    # refinement run (performance).
    campaign_id: str | None = None
    generation_run_id: str | None = None


class AgentJobsProcessResponse(BaseModel):
    processed: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)
