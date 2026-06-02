from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.auth import require_user_context
from app.core.settings import MissingSettingsError
from app.schemas.performance import (
    CampaignPerformanceResponse,
    OptimizationProposalCreate,
    OptimizationProposalResponse,
    PerformanceSnapshotCreate,
    PerformanceSnapshotResponse,
)
from app.services.banners.performance_service import (
    CampaignNotFound,
    InvalidPerformanceMetric,
    PerformanceService,
    configured_service_for_team,
)

router = APIRouter(tags=["performance"])
CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]


def _service_for_request(request: Request) -> PerformanceService:
    context = require_user_context(request)
    return configured_service_for_team(context.team_id)


@router.get("/campaigns/{campaign_id}/performance", response_model=CampaignPerformanceResponse)
def get_campaign_performance(campaign_id: CampaignIdPath, request: Request) -> CampaignPerformanceResponse:
    try:
        return _service_for_request(request).get_campaign_performance(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/campaigns/{campaign_id}/performance/snapshots", response_model=PerformanceSnapshotResponse)
def create_performance_snapshot(campaign_id: CampaignIdPath, payload: PerformanceSnapshotCreate, request: Request) -> PerformanceSnapshotResponse:
    try:
        return _service_for_request(request).create_snapshot(str(campaign_id), payload)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidPerformanceMetric as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/campaigns/{campaign_id}/optimization-proposals", response_model=OptimizationProposalResponse)
def create_optimization_proposal(campaign_id: CampaignIdPath, payload: OptimizationProposalCreate, request: Request) -> OptimizationProposalResponse:
    try:
        return _service_for_request(request).create_proposal(str(campaign_id), payload)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
