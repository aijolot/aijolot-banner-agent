"""Campaign CRUD endpoints (GH-28).

    GET   /campaigns/{id}   -> full Campaign
    PATCH /campaigns/{id}   -> partial update of the structured brief
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.campaign import BriefPatch, Campaign
from app.services import campaign_store

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: str) -> Campaign:
    c = campaign_store.get_campaign(campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"campaign '{campaign_id}' not found")
    return c


@router.patch("/{campaign_id}", response_model=Campaign)
def patch_campaign(campaign_id: str, patch: BriefPatch) -> Campaign:
    c = campaign_store.apply_patch(campaign_id, patch.model_dump(exclude_none=True))
    if not c:
        raise HTTPException(status_code=404, detail=f"campaign '{campaign_id}' not found")
    return c
