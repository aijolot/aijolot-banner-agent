from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path

from app.core.settings import MissingSettingsError
from app.schemas.schedules import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from app.services.banners.schedule_service import (
    CampaignNotApproved,
    CampaignNotFound,
    CampaignRevisionNotFound,
    InvalidScheduleWindow,
    ScheduleNotFound,
    ScheduleService,
    ScheduleServiceUnavailable,
    configured_service,
)

router = APIRouter(tags=["schedules"])
CampaignIdPath = Annotated[UUID, Path(description="Campaign UUID")]


def _schedule_service() -> ScheduleService:
    return configured_service()


@router.post("/campaigns/{campaign_id}/schedule", response_model=ScheduleResponse)
def schedule_campaign(campaign_id: CampaignIdPath, request: ScheduleCreate) -> ScheduleResponse:
    try:
        return _schedule_service().schedule_campaign(str(campaign_id), request)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CampaignRevisionNotFound as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except CampaignNotApproved as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except InvalidScheduleWindow as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (MissingSettingsError, ScheduleServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.patch("/campaigns/{campaign_id}/schedule", response_model=ScheduleResponse)
def update_schedule(campaign_id: CampaignIdPath, request: ScheduleUpdate) -> ScheduleResponse:
    try:
        return _schedule_service().update_schedule(str(campaign_id), request)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScheduleNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidScheduleWindow as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (MissingSettingsError, ScheduleServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/campaigns/{campaign_id}/schedule/cancel", response_model=ScheduleResponse)
def cancel_schedule(campaign_id: CampaignIdPath) -> ScheduleResponse:
    try:
        return _schedule_service().cancel_schedule(str(campaign_id))
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScheduleNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (MissingSettingsError, ScheduleServiceUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
