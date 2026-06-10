from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, Field, ValidationError

from app.core.auth import require_user_context
from app.core.settings import MissingSettingsError
from app.schemas.brand import BrandContext, BrandSummary
from app.schemas.palette_suggestions import PaletteSuggestionResponse, PaletteSuggestionRouteRequest
from app.services import brand_store
from app.services.brands import brand_discovery_service
from app.services.brands.brand_discovery_service import (
    BrandDiscoveryRunPayload,
    BrandDiscoveryService,
    DiscoveryPersistenceUnavailable,
    DiscoveryRunCreateRequest,
    DiscoveryUnavailable,
    StoreNotFound,
)
from app.services.brands.markdown_importer import BrandMarkdownImportError
from app.services.brands.palette_suggestions import PaletteSuggestionService, PaletteSuggestionUnavailable

router = APIRouter(prefix="/brands", tags=["brands"])


class BrandImportRequest(BaseModel):
    brand_id: str | None = Field(default=None, pattern=r"^[a-z0-9_-]+$")
    path: str | None = None


def _service(request: Request):
    context = require_user_context(request)
    return brand_store.service_for_team(context.team_id)


def _discovery_service(request: Request) -> BrandDiscoveryService:
    """Request-scoped discovery service: team from auth context, Shopify Admin
    client + Supabase repositories resolved from the environment (same pattern
    as the other v1 Shopify routes)."""

    context = require_user_context(request)
    return brand_discovery_service.configured_discovery_service(team_id=context.team_id)


@router.get("", response_model=list[BrandSummary])
def list_brands(request: Request) -> list[BrandSummary]:
    return _service(request).list_brands()


@router.post("/import", response_model=BrandContext)
def import_brand(request: Request, payload: BrandImportRequest) -> BrandContext:
    try:
        return _service(request).import_markdown(brand_id=payload.brand_id, path=payload.path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="brand markdown file not found")
    except (BrandMarkdownImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


BrandIdPath = Annotated[str, Path(pattern=r"^[a-z0-9_-]+$")]


@router.get("/{brand_id}", response_model=BrandContext)
def get_brand(request: Request, brand_id: BrandIdPath) -> BrandContext:
    try:
        return _service(request).get_brand(brand_id)
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")


@router.put("/{brand_id}", response_model=BrandContext)
def put_brand(request: Request, brand_id: BrandIdPath, brand: BrandContext) -> BrandContext:
    try:
        return _service(request).save_brand(brand_id, brand)
    except (BrandMarkdownImportError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{brand_id}/palette-suggestions", response_model=PaletteSuggestionResponse)
async def suggest_palette(
    request: Request,
    brand_id: BrandIdPath,
    payload: PaletteSuggestionRouteRequest,
) -> PaletteSuggestionResponse:
    try:
        return await PaletteSuggestionService(_service(request)).suggest(brand_id, payload)
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")
    except PaletteSuggestionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


RunIdPath = Annotated[UUID, Path(description="Discovery run UUID")]


@router.post("/{brand_id}/discovery-runs", response_model=BrandDiscoveryRunPayload)
def start_discovery_run(
    request: Request,
    brand_id: BrandIdPath,
    payload: DiscoveryRunCreateRequest | None = None,
) -> dict:
    """Run Shopify brand discovery synchronously for the request team's brand."""

    service = _discovery_service(request)
    try:
        return service.start_run(brand_id, store_id=payload.store_id if payload else None)
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (DiscoveryUnavailable, DiscoveryPersistenceUnavailable, MissingSettingsError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/{brand_id}/discovery-runs/{run_id}", response_model=BrandDiscoveryRunPayload)
def get_discovery_run(request: Request, brand_id: BrandIdPath, run_id: RunIdPath) -> dict:
    service = _discovery_service(request)
    try:
        run = service.get_run(str(run_id), brand_id=brand_id)
    except (DiscoveryPersistenceUnavailable, MissingSettingsError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if run is None:
        raise HTTPException(status_code=404, detail=f"discovery run '{run_id}' not found")
    return run
