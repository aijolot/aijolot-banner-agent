"""Top-level router for the canonical /api/v1 namespace."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import approvals, art, art_direction, backgrounds, brands, calendar, campaigns, catalog, generation, intake, performance, placements, previews, publishing, schedules, scheduler, stores, suggestions

router = APIRouter(prefix="/api/v1")

router.include_router(brands.router)
router.include_router(intake.router)
router.include_router(campaigns.router)
router.include_router(stores.router)
router.include_router(placements.router)
router.include_router(catalog.router)
router.include_router(art_direction.router)
router.include_router(backgrounds.router)
router.include_router(art.router)
router.include_router(generation.router)
router.include_router(previews.router)
router.include_router(approvals.router)
router.include_router(schedules.router)
router.include_router(publishing.router)
router.include_router(performance.router)
router.include_router(scheduler.router)
router.include_router(suggestions.router)
router.include_router(calendar.router)

__all__ = ["router"]
