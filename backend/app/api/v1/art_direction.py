"""Campaign art-direction endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.auth import require_user_context
from app.core.settings import MissingSettingsError
from app.schemas.art_direction import ArtDirectionResponse, ArtDirectionUpsert
from app.services.banners.art_direction_service import (
    ArtDirectionNotFound,
    ArtDirectionService,
    CampaignNotFound,
    configured_service,
    configured_service_for_team,
)

router = APIRouter(tags=["art-direction"])

CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]


def _default_service() -> ArtDirectionService:
    return configured_service()


_DEFAULT_SERVICE_FACTORY = _default_service


def _service_for_request(request: Request) -> ArtDirectionService:
    context = require_user_context(request)
    if _default_service is _DEFAULT_SERVICE_FACTORY:
        return configured_service_for_team(context.team_id)
    return _default_service()


@router.put("/campaigns/{campaign_id}/art-direction", response_model=ArtDirectionResponse)
def save_campaign_art_direction(campaign_id: CampaignIdPath, request: ArtDirectionUpsert, http_request: Request) -> ArtDirectionResponse:
    try:
        return _service_for_request(http_request).save_art_direction(str(campaign_id), request)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ArtDirectionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.get("/campaigns/{campaign_id}/art-direction", response_model=ArtDirectionResponse)
def get_campaign_art_direction(campaign_id: CampaignIdPath, request: Request) -> ArtDirectionResponse:
    try:
        return _service_for_request(request).get_art_direction(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ArtDirectionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
