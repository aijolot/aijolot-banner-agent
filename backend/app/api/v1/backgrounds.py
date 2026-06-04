"""Campaign AI background-options endpoint (F7)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.auth import require_user_context
from app.core.settings import MissingSettingsError
from app.schemas.backgrounds import BackgroundOptionsRequest, BackgroundOptionsResponse
from app.services.banners.background_service import (
    BackgroundOptionsService,
    CampaignNotFound,
    RevisionNotFound,
    configured_service,
    configured_service_for_team,
)

router = APIRouter(tags=["backgrounds"])

CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]


def _default_service() -> BackgroundOptionsService:
    return configured_service()


_DEFAULT_SERVICE_FACTORY = _default_service


def _service_for_request(request: Request) -> BackgroundOptionsService:
    context = require_user_context(request)
    if _default_service is _DEFAULT_SERVICE_FACTORY:
        return configured_service_for_team(context.team_id)
    return _default_service()


@router.post("/campaigns/{campaign_id}/background-options", response_model=BackgroundOptionsResponse)
def generate_background_options(
    campaign_id: CampaignIdPath,
    http_request: Request,
    request: BackgroundOptionsRequest | None = None,
) -> BackgroundOptionsResponse:
    try:
        return _service_for_request(http_request).generate_options(
            str(campaign_id), request or BackgroundOptionsRequest()
        )
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except RevisionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
