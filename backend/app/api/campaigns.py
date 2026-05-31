"""Campaign CRUD endpoints (GH-28).

    GET   /campaigns/{id}   -> full Campaign
    PATCH /campaigns/{id}   -> partial update of the structured brief

TODO(Task 19): these MVP routes currently use configured-team service-role
access. Add auth and request-scoped team/store/user context before exposing
them outside the trusted demo backend.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.campaign import BriefPatch, Campaign
from app.services import campaign_store
from app.services.banners.campaign_service import CampaignNotEditable

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    title: str | None = None
    raw_brief: str | None = None


@router.post("", response_model=Campaign)
def create_campaign(payload: CampaignCreate | None = None) -> Campaign:
    payload = payload or CampaignCreate()
    return campaign_store.create_campaign(title=payload.title or "", raw_brief=payload.raw_brief or "")


@router.get("", response_model=list[Campaign])
def list_campaigns() -> list[Campaign]:
    return campaign_store.list_campaigns()


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: str) -> Campaign:
    c = campaign_store.get_campaign(campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"campaign '{campaign_id}' not found")
    return c


@router.patch("/{campaign_id}", response_model=Campaign)
def patch_campaign(campaign_id: str, patch: BriefPatch) -> Campaign:
    try:
        c = campaign_store.apply_patch(campaign_id, patch.model_dump(exclude_none=True))
    except CampaignNotEditable:
        raise HTTPException(status_code=409, detail=f"campaign '{campaign_id}' is not editable") from None
    if not c:
        raise HTTPException(status_code=404, detail=f"campaign '{campaign_id}' not found")
    return c
