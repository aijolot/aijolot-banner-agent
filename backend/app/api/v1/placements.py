"""Placement registry and campaign placement endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.auth import require_user_context
from app.core.settings import MissingSettingsError
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
    configured_service_for_team,
)
from app.services.shopify.resource_service import StoreNotFound

router = APIRouter(tags=["placements"])

StoreIdPath = Annotated[UUID, Path(description="Store UUID")]
CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]
PlacementTypeKeyPath = Annotated[str, Path(min_length=1, description="Placement type key")]


def _default_service() -> PlacementService:
    return configured_service()


_DEFAULT_SERVICE_FACTORY = _default_service


def _service_for_request(request: Request) -> PlacementService:
    context = require_user_context(request)
    if _default_service is _DEFAULT_SERVICE_FACTORY:
        return configured_service_for_team(context.team_id)
    return _default_service()


@router.get("/stores/{store_id}/placement-types", response_model=list[PlacementTypeSummary])
def list_placement_types(store_id: StoreIdPath, request: Request) -> list[PlacementTypeSummary]:
    try:
        return _service_for_request(request).list_placement_types(str(store_id))
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.get("/stores/{store_id}/placement-types/{placement_type_key}/targets", response_model=PlacementTargetMap)
def list_placement_targets(store_id: StoreIdPath, placement_type_key: PlacementTypeKeyPath, request: Request) -> PlacementTargetMap:
    try:
        return _service_for_request(request).list_targets(str(store_id), placement_type_key)
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")
    except PlacementTypeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.post("/placements/validate", response_model=PlacementValidationResponse)
def validate_placement(request: PlacementValidateRequest, http_request: Request) -> PlacementValidationResponse:
    try:
        return _service_for_request(http_request).validate(request)
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PlacementTypeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidPlacement as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.post("/campaigns/{campaign_id}/placement", response_model=CampaignPlacementResponse)
def save_campaign_placement(campaign_id: CampaignIdPath, request: CampaignPlacementUpsert, http_request: Request) -> CampaignPlacementResponse:
    try:
        return _service_for_request(http_request).save_campaign_placement(str(campaign_id), request)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PlacementTypeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidPlacement as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.get("/campaigns/{campaign_id}/placement", response_model=CampaignPlacementResponse)
def get_campaign_placement(campaign_id: CampaignIdPath, request: Request) -> CampaignPlacementResponse:
    try:
        return _service_for_request(request).get_campaign_placement(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CampaignPlacementNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
