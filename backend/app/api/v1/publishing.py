from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.auth import require_user_context
from app.schemas.schedules import PublishJobResponse
from app.services.shopify.publisher import (
    CampaignNotFound,
    CampaignRevisionNotFound,
    CampaignNotScheduled,
    PublishUnsupported,
    PublisherUnavailable,
    ShopifyPublisher,
    StoreNotFound,
    configured_publisher,
)

router = APIRouter(tags=["publishing"])
CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]
StoreIdPath = Annotated[UUID, Path(description="Store UUID")]


def _publisher() -> ShopifyPublisher:
    return configured_publisher()


_DEFAULT_PUBLISHER_FACTORY = _publisher


def _publisher_for_request(request: Request) -> ShopifyPublisher:
    """Build a request-scoped publisher, or use a test-overridden factory."""

    if _publisher is _DEFAULT_PUBLISHER_FACTORY:
        context = require_user_context(request)
        return configured_publisher(team_id=context.team_id)
    return _publisher()


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, (CampaignNotFound, StoreNotFound)):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (CampaignRevisionNotFound, CampaignNotScheduled)):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, PublishUnsupported):
        raise HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, PublisherUnavailable):
        raise HTTPException(status_code=503, detail=str(exc))
    raise exc


@router.post("/campaigns/{campaign_id}/publish", response_model=PublishJobResponse)
def publish_campaign(campaign_id: CampaignIdPath, request: Request) -> PublishJobResponse:
    try:
        return _publisher_for_request(request).publish_campaign(str(campaign_id))
    except (CampaignNotFound, CampaignRevisionNotFound, CampaignNotScheduled, StoreNotFound, PublishUnsupported, PublisherUnavailable) as exc:
        _raise_http(exc)


@router.post("/campaigns/{campaign_id}/unpublish", response_model=PublishJobResponse)
def unpublish_campaign(campaign_id: CampaignIdPath, request: Request) -> PublishJobResponse:
    try:
        return _publisher_for_request(request).unpublish_campaign(str(campaign_id))
    except (CampaignNotFound, CampaignRevisionNotFound, CampaignNotScheduled, StoreNotFound, PublishUnsupported, PublisherUnavailable) as exc:
        _raise_http(exc)


@router.post("/stores/{store_id}/shopify/install-theme-files", response_model=PublishJobResponse)
def install_theme_files(store_id: StoreIdPath, request: Request) -> PublishJobResponse:
    try:
        return _publisher_for_request(request).install_theme_files(str(store_id))
    except (StoreNotFound, PublishUnsupported, PublisherUnavailable) as exc:
        _raise_http(exc)
