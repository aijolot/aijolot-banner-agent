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


def _publisher() -> ShopifyPublisher:
    return configured_publisher()


_DEFAULT_PUBLISHER_FACTORY = _publisher


def _require_context_when_default(request: Request) -> None:
    if _publisher is _DEFAULT_PUBLISHER_FACTORY:
        require_user_context(request)


@router.post("/campaigns/{campaign_id}/publish", response_model=PublishJobResponse)
def publish_campaign(campaign_id: CampaignIdPath, request: Request) -> PublishJobResponse:
    try:
        _require_context_when_default(request)
        return _publisher().publish_campaign(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (CampaignRevisionNotFound, CampaignNotScheduled) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PublishUnsupported as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PublisherUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/campaigns/{campaign_id}/unpublish", response_model=PublishJobResponse)
def unpublish_campaign(campaign_id: CampaignIdPath, request: Request) -> PublishJobResponse:
    try:
        _require_context_when_default(request)
        return _publisher().unpublish_campaign(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (CampaignRevisionNotFound, CampaignNotScheduled) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PublishUnsupported as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except PublisherUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
