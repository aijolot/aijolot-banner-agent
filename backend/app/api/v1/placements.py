"""Placement registry and campaign placement endpoints.

TODO(Task 19): these MVP routes currently use configured-team service-role
access in Supabase mode. Add auth and request-scoped team/store/user context
before exposing them outside the trusted demo backend.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path

from app.schemas.placements import (
    CampaignPlacementResponse,
    CampaignPlacementUpsert,
    PlacementTargetMap,
    PlacementTypeSummary,
    PlacementValidateRequest,
    PlacementValidationResponse,
)
from app.services.banners.placement_service import (
    CampaignNotFound,
    CampaignPlacementNotFound,
    InvalidPlacement,
    PlacementService,
    PlacementTypeNotFound,
    configured_service,
)
from app.services.shopify.resource_service import StoreNotFound

router = APIRouter(tags=["placements"])

StoreIdPath = Annotated[UUID, Path(description="Store UUID")]
CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]
PlacementTypeKeyPath = Annotated[str, Path(min_length=1, description="Placement type key")]


def _default_service() -> PlacementService:
    return configured_service()


@router.get("/stores/{store_id}/placement-types", response_model=list[PlacementTypeSummary])
def list_placement_types(store_id: StoreIdPath) -> list[PlacementTypeSummary]:
    try:
        return _default_service().list_placement_types(str(store_id))
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")


@router.get("/stores/{store_id}/placement-types/{placement_type_key}/targets", response_model=PlacementTargetMap)
def list_placement_targets(store_id: StoreIdPath, placement_type_key: PlacementTypeKeyPath) -> PlacementTargetMap:
    try:
        return _default_service().list_targets(str(store_id), placement_type_key)
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")
    except PlacementTypeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/placements/validate", response_model=PlacementValidationResponse)
def validate_placement(request: PlacementValidateRequest) -> PlacementValidationResponse:
    try:
        return _default_service().validate(request)
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PlacementTypeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidPlacement as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/campaigns/{campaign_id}/placement", response_model=CampaignPlacementResponse)
def save_campaign_placement(campaign_id: CampaignIdPath, request: CampaignPlacementUpsert) -> CampaignPlacementResponse:
    try:
        return _default_service().save_campaign_placement(str(campaign_id), request)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PlacementTypeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidPlacement as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/campaigns/{campaign_id}/placement", response_model=CampaignPlacementResponse)
def get_campaign_placement(campaign_id: CampaignIdPath) -> CampaignPlacementResponse:
    try:
        return _default_service().get_campaign_placement(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CampaignPlacementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
