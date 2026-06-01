from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request

from app.core.auth import require_user_context
from app.schemas.stores import ShopifyResourceSummary, ShopifyResourceType, StoreSummary
from app.services.shopify.resource_service import ShopifyResourceService, StoreNotFound, configured_service, configured_service_for_team

router = APIRouter(prefix="/stores", tags=["stores"])

StoreIdPath = Annotated[UUID, Path(description="Store UUID")]
ResourceTypeQuery = Annotated[ShopifyResourceType, Query(description="Selectable Shopify resource type")]


def _default_service() -> ShopifyResourceService:
    return configured_service()


def _service_for_request(request: Request) -> ShopifyResourceService:
    if _default_service is _DEFAULT_SERVICE_FACTORY:
        context = require_user_context(request)
        return configured_service_for_team(context.team_id)
    return _default_service()


_DEFAULT_SERVICE_FACTORY = _default_service


@router.get("", response_model=list[StoreSummary])
def list_stores(request: Request) -> list[StoreSummary]:
    return _service_for_request(request).list_stores()


@router.get("/{store_id}", response_model=StoreSummary)
def get_store(store_id: StoreIdPath, request: Request) -> StoreSummary:
    try:
        return _service_for_request(request).get_store(str(store_id))
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")


@router.get("/{store_id}/shopify/resources", response_model=list[ShopifyResourceSummary])
def list_shopify_resources(store_id: StoreIdPath, resource_type: ResourceTypeQuery, request: Request) -> list[ShopifyResourceSummary]:
    try:
        return _service_for_request(request).list_resources(str(store_id), resource_type=resource_type)
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")
