from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query

from app.schemas.stores import ShopifyResourceSummary, ShopifyResourceType, StoreSummary
from app.services.shopify.resource_service import ShopifyResourceService, StoreNotFound, configured_service

router = APIRouter(prefix="/stores", tags=["stores"])

StoreIdPath = Annotated[UUID, Path(description="Store UUID")]
ResourceTypeQuery = Annotated[ShopifyResourceType, Query(description="Selectable Shopify resource type")]


def _default_service() -> ShopifyResourceService:
    return configured_service()


@router.get("", response_model=list[StoreSummary])
def list_stores() -> list[StoreSummary]:
    return _default_service().list_stores()


@router.get("/{store_id}", response_model=StoreSummary)
def get_store(store_id: StoreIdPath) -> StoreSummary:
    try:
        return _default_service().get_store(str(store_id))
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")


@router.get("/{store_id}/shopify/resources", response_model=list[ShopifyResourceSummary])
def list_shopify_resources(store_id: StoreIdPath, resource_type: ResourceTypeQuery) -> list[ShopifyResourceSummary]:
    try:
        return _default_service().list_resources(str(store_id), resource_type=resource_type)
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")
