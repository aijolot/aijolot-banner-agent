"""Brand endpoints (GH-26 / GH-17).

    GET  /brands                                                 -> list of brand summaries
    GET  /brands/{id}                                            -> full BrandContext
    PUT  /brands/{id}                                            -> validate + persist, returns the saved BrandContext
    POST /brands/{id}/discovery-runs                             -> run Shopify brand discovery synchronously
    GET  /brands/{id}/discovery-runs/{run_id}                    -> one persisted discovery run
    POST /brands/{id}/discovery-runs/{run_id}/recommendations    -> Gemini color role draft for a run
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field, ValidationError

from app.core.settings import MissingSettingsError
from app.schemas.brand import BrandContext, BrandSummary
from app.schemas.palette_suggestions import PaletteSuggestionResponse, PaletteSuggestionRouteRequest
from app.services import brand_store
from app.services.brands import brand_discovery_service
from app.services.brands.brand_discovery_service import (
    BrandDiscoveryRunPayload,
    DiscoveryPersistenceUnavailable,
    DiscoveryRunCreateRequest,
    DiscoveryRunMissingSnapshot,
    DiscoveryUnavailable,
    StoreNotFound,
)
from app.services.brands.brand_recommendations import BrandRecommendationUnavailable
from app.services.brands.markdown_importer import BrandMarkdownImportError
from app.services.brands.palette_suggestions import PaletteSuggestionService, PaletteSuggestionUnavailable

router = APIRouter(prefix="/brands", tags=["brands"])


class BrandImportRequest(BaseModel):
    brand_id: str | None = Field(default=None, pattern=r"^[a-z0-9_-]+$")
    path: str | None = None


@router.get("", response_model=list[BrandSummary])
def list_brands() -> list[BrandSummary]:
    return brand_store.list_brands()


@router.post("/import", response_model=BrandContext)
def import_brand(request: BrandImportRequest) -> BrandContext:
    try:
        return brand_store.import_markdown_brand(brand_id=request.brand_id, path=request.path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="brand markdown file not found")
    except (BrandMarkdownImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


BrandIdPath = Annotated[str, Path(pattern=r"^[a-z0-9_-]+$")]


@router.get("/{brand_id}", response_model=BrandContext)
def get_brand(brand_id: BrandIdPath) -> BrandContext:
    try:
        return brand_store.get_brand(brand_id)
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")


@router.put("/{brand_id}", response_model=BrandContext)
def put_brand(brand_id: BrandIdPath, brand: BrandContext) -> BrandContext:
    # Pydantic already validated the body (hex colors, arrays, etc.).
    try:
        return brand_store.save_brand(brand_id, brand)
    except (BrandMarkdownImportError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{brand_id}/palette-suggestions", response_model=PaletteSuggestionResponse)
async def suggest_palette(brand_id: BrandIdPath, request: PaletteSuggestionRouteRequest) -> PaletteSuggestionResponse:
    try:
        return await PaletteSuggestionService(brand_store._default_service()).suggest(brand_id, request)
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")
    except PaletteSuggestionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


RunIdPath = Annotated[UUID, Path(description="Discovery run UUID")]


@router.post("/{brand_id}/discovery-runs", response_model=BrandDiscoveryRunPayload)
def start_discovery_run(brand_id: BrandIdPath, request: DiscoveryRunCreateRequest | None = None) -> dict:
    """Run Shopify brand discovery synchronously (default demo service wiring)."""

    try:
        service = brand_discovery_service.configured_discovery_service()
        return service.start_run(brand_id, store_id=request.store_id if request else None)
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (DiscoveryUnavailable, DiscoveryPersistenceUnavailable, MissingSettingsError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/{brand_id}/discovery-runs/{run_id}", response_model=BrandDiscoveryRunPayload)
def get_discovery_run(brand_id: BrandIdPath, run_id: RunIdPath) -> dict:
    try:
        service = brand_discovery_service.configured_discovery_service()
        run = service.get_run(str(run_id), brand_id=brand_id)
    except (DiscoveryPersistenceUnavailable, MissingSettingsError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if run is None:
        raise HTTPException(status_code=404, detail=f"discovery run '{run_id}' not found")
    return run


@router.post("/{brand_id}/discovery-runs/{run_id}/recommendations", response_model=BrandDiscoveryRunPayload)
async def recommend_discovery_colors(brand_id: BrandIdPath, run_id: RunIdPath) -> dict:
    """Turn a run's discovery evidence into a Gemini-backed color role draft and persist it."""

    try:
        service = brand_discovery_service.configured_discovery_service()
        run = await service.recommend_colors_for_run(brand_id, str(run_id))
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")
    except DiscoveryRunMissingSnapshot as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except BrandRecommendationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (DiscoveryPersistenceUnavailable, MissingSettingsError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if run is None:
        raise HTTPException(status_code=404, detail=f"discovery run '{run_id}' not found")
    return run
