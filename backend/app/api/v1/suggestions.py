"""/api/v1 proactive agent suggestions + agent-jobs poller (Fase 0).

GET  /suggestions                   — pending (default) suggestions for the team
POST /suggestions/{id}/accept       — calendar/catalog → create campaign with the
                                      prefilled brief; performance → refinement run
POST /suggestions/{id}/dismiss
GET  /agent-jobs/process            — backend-poll side of the pg_cron scan queue
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from app.core.auth import UserContext, require_user_context
from app.core.dependencies import get_supabase_client_factory
from app.core.settings import MissingSettingsError
from app.db.repositories.agent_jobs import AgentJobRepository
from app.schemas.campaign import StructuredBrief
from app.schemas.suggestions import (
    AgentJobsProcessResponse,
    AgentSuggestionResponse,
    SuggestionAcceptRequest,
    SuggestionAcceptResponse,
    SuggestionListResponse,
)
from app.services import campaign_store
from app.services.banners.agent_job_runner import AgentJobRunner
from app.services.banners.suggestion_service import (
    SuggestionNotActionable,
    SuggestionNotFound,
    SuggestionService,
    configured_service_for_team,
)
from app.services.supabase.client import SupabaseClientFactory

router = APIRouter(tags=["suggestions"])
SuggestionIdPath = Annotated[UUID, Path(description="Suggestion UUID")]

# Scan handlers, registered by their owning features (F1/F2/F3) at import time.
JOB_HANDLERS: dict[str, Any] = {}


def _create_campaign_callback(context: UserContext):
    """calendar/catalog accept → a draft campaign with the suggested brief."""

    def _create(payload: dict[str, Any]) -> str:
        service = campaign_store.get_service_for_context(context)
        brief_data = dict(payload.get("structured_brief") or {})
        brief = StructuredBrief.model_validate(brief_data) if brief_data else None
        campaign = service.create_campaign(
            title=str(payload.get("title") or "Campaña sugerida por el agente"),
            raw_brief=str(payload.get("raw_brief") or ""),
            structured_brief=brief,
        )
        return str(campaign.id)

    return _create


def _service_for_request(request: Request) -> SuggestionService:
    context = require_user_context(request)
    return configured_service_for_team(
        context.team_id,
        create_campaign=_create_campaign_callback(context),
        # start_refinement is wired by F2 (performance loop) — accepting a
        # performance_refresh before that lands returns 503 honestly.
    )


@router.get("/suggestions", response_model=SuggestionListResponse)
def list_suggestions(
    request: Request,
    status: Annotated[str | None, Query(pattern="^(pending|accepted|dismissed|expired|all)$")] = "pending",
    kind: Annotated[str | None, Query(pattern="^(calendar_event|performance_refresh|catalog_signal)$")] = None,
) -> SuggestionListResponse:
    try:
        service = _service_for_request(request)
        service.expire_stale()
        return SuggestionListResponse(
            suggestions=service.list(status=None if status == "all" else status, kind=kind)
        )
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/suggestions/{suggestion_id}/accept", response_model=SuggestionAcceptResponse)
def accept_suggestion(
    suggestion_id: SuggestionIdPath, request: Request, payload: SuggestionAcceptRequest | None = None
) -> SuggestionAcceptResponse:
    try:
        return _service_for_request(request).accept(str(suggestion_id))
    except SuggestionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SuggestionNotActionable as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/suggestions/{suggestion_id}/dismiss", response_model=AgentSuggestionResponse)
def dismiss_suggestion(suggestion_id: SuggestionIdPath, request: Request) -> AgentSuggestionResponse:
    try:
        return _service_for_request(request).dismiss(str(suggestion_id))
    except SuggestionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except SuggestionNotActionable as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/agent-jobs/process", response_model=AgentJobsProcessResponse)
def process_agent_jobs(
    factory: Annotated[SupabaseClientFactory, Depends(get_supabase_client_factory)],
) -> AgentJobsProcessResponse:
    client = factory.service_role_client()
    runner = AgentJobRunner(jobs=AgentJobRepository(client), handlers=JOB_HANDLERS)
    results = runner.run_processing_jobs()
    return AgentJobsProcessResponse(processed=len(results), items=results)
