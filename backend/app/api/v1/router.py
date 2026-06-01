"""Top-level router for the canonical /api/v1 namespace."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import art_direction, brands, campaigns, catalog, generation, intake, placements, previews, stores

router = APIRouter(prefix="/api/v1")

router.include_router(brands.router)
router.include_router(intake.router)
router.include_router(campaigns.router)
router.include_router(stores.router)
router.include_router(placements.router)
router.include_router(catalog.router)
router.include_router(art_direction.router)
router.include_router(generation.router)
router.include_router(previews.router)

__all__ = ["router"]
