"""Scheduler poller — backend-poll side of the publish pipeline.

pg_cron runs every minute, marks pending+due scheduled_banners rows as 'processing'
(via publish_due_banners_fn), and this endpoint then picks them up and marks them
'published'. In production a real ShopifyPublisher would replace the mark_published
call; for the hackathon demo the publish step is simulated.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_supabase_client_factory
from app.db.repositories.scheduled_banners import ScheduledBannerRepository
from app.services.supabase.client import SupabaseClientFactory

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/process")
def process_due_scheduled_banners(
    factory: Annotated[SupabaseClientFactory, Depends(get_supabase_client_factory)],
) -> dict:
    client = factory.service_role_client()
    repo = ScheduledBannerRepository(client)
    processing = repo.list_processing()
    results: list[dict] = []
    for row in processing:
        updated = repo.mark_published(row["id"])
        results.append({"id": row["id"], "status": "published", "row": updated})
    return {"processed": len(results), "items": results}
