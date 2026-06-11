"""Campaign catalog snapshot endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.auth import require_user_context
from app.core.settings import MissingSettingsError
from app.schemas.catalog import CatalogSnapshotCreate, CatalogSnapshotResponse
from app.services.banners.catalog_snapshot_service import (
    CampaignCatalogSnapshotNotFound,
    CampaignNotFound,
    CatalogSnapshotService,
    InvalidCatalogSnapshot,
    configured_service,
    configured_service_for_team,
)
from app.services.shopify.resource_service import StoreNotFound

router = APIRouter(tags=["catalog"])
CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]


def _default_service() -> CatalogSnapshotService:
    return configured_service()


_DEFAULT_SERVICE_FACTORY = _default_service


def _service_for_request(request: Request) -> CatalogSnapshotService:
    context = require_user_context(request)
    if _default_service is _DEFAULT_SERVICE_FACTORY:
        return configured_service_for_team(context.team_id)
    return _default_service()


@router.post("/campaigns/{campaign_id}/catalog-snapshot", response_model=CatalogSnapshotResponse)
def create_catalog_snapshot(campaign_id: CampaignIdPath, http_request: Request, request: CatalogSnapshotCreate | None = None) -> CatalogSnapshotResponse:
    request = request or CatalogSnapshotCreate()
    try:
        return _service_for_request(http_request).create_snapshot(
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
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.get("/campaigns/{campaign_id}/catalog-snapshot", response_model=CatalogSnapshotResponse)
def get_catalog_snapshot(campaign_id: CampaignIdPath, request: Request) -> CatalogSnapshotResponse:
    try:
        return _service_for_request(request).get_snapshot(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CampaignCatalogSnapshotNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except MissingSettingsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


@router.get("/catalog/signals")
def list_catalog_signals(request: Request) -> dict:
    """F3 — materialized catalog signals for the team (read-only)."""
    from app.core.settings import Settings
    from app.services.banners.catalog_signal_service import InMemoryCatalogSignals, SupabaseCatalogSignals
    from app.services.supabase.client import SupabaseClientFactory

    context = require_user_context(request)
    settings = Settings.from_env()
    if settings.supabase_url and settings.supabase_service_role_key:
        client = SupabaseClientFactory(settings).service_role_client()
        signals = SupabaseCatalogSignals(client).list(team_id=context.team_id)
    else:
        signals = InMemoryCatalogSignals().list(team_id=context.team_id)
    return {"signals": signals}
