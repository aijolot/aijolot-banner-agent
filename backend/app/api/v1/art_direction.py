"""Campaign art-direction endpoints.

TODO(Task 19): these MVP routes currently use configured-team service-role
access in Supabase mode. Add auth and request-scoped team/store/user context
before exposing them outside the trusted demo backend.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path

from app.schemas.art_direction import ArtDirectionResponse, ArtDirectionUpsert
from app.services.banners.art_direction_service import (
    ArtDirectionNotFound,
    ArtDirectionService,
    CampaignNotFound,
    configured_service,
)

router = APIRouter(tags=["art-direction"])

CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]


def _default_service() -> ArtDirectionService:
    return configured_service()


@router.put("/campaigns/{campaign_id}/art-direction", response_model=ArtDirectionResponse)
def save_campaign_art_direction(campaign_id: CampaignIdPath, request: ArtDirectionUpsert) -> ArtDirectionResponse:
    try:
        return _default_service().save_art_direction(str(campaign_id), request)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ArtDirectionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/campaigns/{campaign_id}/art-direction", response_model=ArtDirectionResponse)
def get_campaign_art_direction(campaign_id: CampaignIdPath) -> ArtDirectionResponse:
    try:
        return _default_service().get_art_direction(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ArtDirectionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
