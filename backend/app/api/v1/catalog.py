"""Campaign catalog snapshot endpoints.

TODO(Task 19): these MVP routes currently use configured-team service-role
access in Supabase mode. Add auth and request-scoped team/store/user context
before exposing them outside the trusted demo backend.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path

from app.schemas.catalog import CatalogSnapshotCreate, CatalogSnapshotResponse
from app.services.banners.catalog_snapshot_service import (
    CampaignCatalogSnapshotNotFound,
    CampaignNotFound,
    CatalogSnapshotService,
    InvalidCatalogSnapshot,
    configured_service,
)
from app.services.shopify.resource_service import StoreNotFound

router = APIRouter(tags=["catalog"])
CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]


def _default_service() -> CatalogSnapshotService:
    return configured_service()


@router.post("/campaigns/{campaign_id}/catalog-snapshot", response_model=CatalogSnapshotResponse)
def create_catalog_snapshot(campaign_id: CampaignIdPath, request: CatalogSnapshotCreate | None = None) -> CatalogSnapshotResponse:
    request = request or CatalogSnapshotCreate()
    try:
        return _default_service().create_snapshot(
            str(campaign_id),
            store_id=request.store_id,
            query_summary=request.query_summary,
            discount_rule=request.discount_rule,
            resource_types=request.resource_types,
            limit=request.limit,
        )
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidCatalogSnapshot as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/campaigns/{campaign_id}/catalog-snapshot", response_model=CatalogSnapshotResponse)
def get_catalog_snapshot(campaign_id: CampaignIdPath) -> CatalogSnapshotResponse:
    try:
        return _default_service().get_snapshot(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CampaignCatalogSnapshotNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
