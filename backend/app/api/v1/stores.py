from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import require_user_context
from app.core.settings import MissingSettingsError
from app.schemas.stores import ShopifyResourceSummary, ShopifyResourceType, StoreSummary, SyncReport
from app.services.shopify.resource_service import ShopifyResourceService, StoreNotFound, configured_service, configured_service_for_team

router = APIRouter(prefix="/stores", tags=["stores"])

StoreIdPath = Annotated[UUID, Path(description="Store UUID")]
ResourceTypeQuery = Annotated[ShopifyResourceType, Query(description="Selectable Shopify resource type")]


class ShopifySyncRequest(BaseModel):
    resource_types: list[str] | None = Field(default=None, description="Subset to sync; defaults to product/collection/vendor/customer_segment")
    dry_run: bool = Field(default=False, description="Fetch + map but do not write the cache")


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
def list_shopify_resources(
    store_id: StoreIdPath,
    resource_type: ResourceTypeQuery,
    request: Request,
    q: Annotated[str | None, Query(description="Filter by title/handle/vendor/tag")] = None,
) -> list[ShopifyResourceSummary]:
    try:
        return _service_for_request(request).list_resources(str(store_id), resource_type=resource_type, query=q)
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")


@router.post("/{store_id}/shopify/sync", response_model=SyncReport)
def sync_shopify_resources(store_id: StoreIdPath, body: ShopifySyncRequest, request: Request) -> SyncReport:
    context = require_user_context(request)
    from app.services.shopify.sync_service import ShopifyCatalogSyncService

    try:
        service = ShopifyCatalogSyncService.from_env(team_id=context.team_id)
        report = service.sync_store(str(store_id), resource_types=body.resource_types, dry_run=body.dry_run)
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except StoreNotFound:
        raise HTTPException(status_code=404, detail=f"store '{store_id}' not found")
    return SyncReport(**report)
