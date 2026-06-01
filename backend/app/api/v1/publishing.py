from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path

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


@router.post("/campaigns/{campaign_id}/publish", response_model=PublishJobResponse)
def publish_campaign(campaign_id: CampaignIdPath) -> PublishJobResponse:
    try:
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
def unpublish_campaign(campaign_id: CampaignIdPath) -> PublishJobResponse:
    try:
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
