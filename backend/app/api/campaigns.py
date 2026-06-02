"""Campaign CRUD endpoints (GH-28).

    GET   /campaigns/{id}   -> full Campaign
    PATCH /campaigns/{id}   -> partial update of the structured brief

Task 19 adds request-scoped context for `/api/v1` when a scoped service is
installed, while preserving root prototype compatibility.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.auth import UserContext, optional_user_context, require_user_context
from app.core.settings import MissingSettingsError
from app.schemas.campaign import BriefPatch, Campaign
from app.services import campaign_store
from app.services.banners.campaign_service import CampaignNotEditable

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CampaignCreate(BaseModel):
    title: str | None = None
    raw_brief: str | None = None


def _is_v1_request(request: Request) -> bool:
    return request.url.path.startswith("/api/v1/")


def _service_for_context(context: UserContext):
    """Build the request-scoped service for a parsed context.

    The default MVP implementation delegates to the existing facade, whose
    Supabase-backed service already scopes repository calls by its configured
    team. Tests can override this seam with fake team-aware services. Full
    Supabase JWT-to-team resolution remains frontend/auth-provider owned.
    """

    return campaign_store.get_service_for_context(context)


_DEFAULT_SERVICE_FOR_CONTEXT = _service_for_context


def _campaign_service(request: Request):
    if _is_v1_request(request):
        context = require_user_context(request)
        try:
            return _service_for_context(context)
        except MissingSettingsError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
    context = optional_user_context(request)
    if context is not None and _service_for_context is not _DEFAULT_SERVICE_FOR_CONTEXT:
        return _service_for_context(context)
    return campaign_store.get_service()


@router.post("", response_model=Campaign)
def create_campaign(payload: CampaignCreate | None = None, service=Depends(_campaign_service)) -> Campaign:
    payload = payload or CampaignCreate()
    return service.create_campaign(title=payload.title or "", raw_brief=payload.raw_brief or "")


@router.get("", response_model=list[Campaign])
def list_campaigns(service=Depends(_campaign_service)) -> list[Campaign]:
    return service.list_campaigns()


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: str, service=Depends(_campaign_service)) -> Campaign:
    c = service.get_campaign(campaign_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"campaign '{campaign_id}' not found")
    return c


@router.patch("/{campaign_id}", response_model=Campaign)
def patch_campaign(campaign_id: str, patch: BriefPatch, service=Depends(_campaign_service)) -> Campaign:
    try:
        c = service.apply_patch(campaign_id, patch.model_dump(exclude_none=True))
    except CampaignNotEditable:
        raise HTTPException(status_code=409, detail=f"campaign '{campaign_id}' is not editable") from None
    if not c:
        raise HTTPException(status_code=404, detail=f"campaign '{campaign_id}' not found")
    return c
