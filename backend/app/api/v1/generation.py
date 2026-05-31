"""Campaign generation run endpoints.

TODO(Task 19): these MVP routes currently use configured-team service-role
access in Supabase mode. Add auth and request-scoped team/store/user context
before exposing them outside the trusted demo backend.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path

from app.schemas.generation import GenerationEventResponse, GenerationRunCreate, GenerationRunResponse
from app.services.banners.generation_run_service import (
    CampaignGenerationRunNotFound,
    CampaignNotFound,
    GenerationRunNotFound,
    GenerationRunService,
    configured_service,
)

router = APIRouter(tags=["generation"])

CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]
RunIdPath = Annotated[UUID, Path(description="Generation run UUID")]


def _default_service() -> GenerationRunService:
    return configured_service()


@router.post("/campaigns/{campaign_id}/generation-runs", response_model=GenerationRunResponse)
def start_generation_run(campaign_id: CampaignIdPath, request: GenerationRunCreate | None = None) -> GenerationRunResponse:
    try:
        return _default_service().start_generation_run(str(campaign_id), request or GenerationRunCreate())
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except GenerationRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/campaigns/{campaign_id}/generation-runs/latest", response_model=GenerationRunResponse)
def get_latest_generation_run(campaign_id: CampaignIdPath) -> GenerationRunResponse:
    try:
        return _default_service().get_latest_for_campaign(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CampaignGenerationRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/generation-runs/{run_id}", response_model=GenerationRunResponse)
def get_generation_run(run_id: RunIdPath) -> GenerationRunResponse:
    try:
        return _default_service().get_run(str(run_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except GenerationRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/generation-runs/{run_id}/events", response_model=list[GenerationEventResponse])
def list_generation_events(run_id: RunIdPath) -> list[GenerationEventResponse]:
    try:
        return _default_service().list_events(str(run_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except GenerationRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
