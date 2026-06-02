from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.campaign_revisions import CampaignRevisionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.db.repositories.schedules import ScheduleRepository
from app.schemas.schedules import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from app.services.supabase.client import SupabaseClientFactory


class ScheduleError(Exception):
    pass


class CampaignNotFound(ScheduleError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign {campaign_id} not found")


class CampaignNotApproved(ScheduleError):
    def __init__(self, campaign_id: str, status: str | None) -> None:
        super().__init__(f"campaign {campaign_id} must be approved before scheduling (current status: {status})")


class CampaignRevisionNotFound(ScheduleError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign {campaign_id} has no selected revision")


class ScheduleNotFound(ScheduleError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign {campaign_id} has no active schedule")


class InvalidScheduleWindow(ScheduleError):
    pass


class ScheduleServiceUnavailable(ScheduleError):
    pass


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise InvalidScheduleWindow(f"invalid datetime: {value}") from exc


class ScheduleService:
    def __init__(self, *, campaigns: Any, revisions: Any = None, schedules: Any, team_id: str | None = None) -> None:
        self.campaigns = campaigns
        self.revisions = revisions
        self.schedules = schedules
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str | None = None) -> "ScheduleService":
        return cls(campaigns=CampaignRepository(client), revisions=CampaignRevisionRepository(client), schedules=ScheduleRepository(client), team_id=team_id)

    def schedule_campaign(self, campaign_id: str, request: ScheduleCreate) -> ScheduleResponse:
        campaign = self._approved_campaign(campaign_id)
        revision_id = request.revision_id or campaign.get("selected_revision_id")
        if request.revision_id and self.revisions:
            revision = self.revisions.get(revision_id=request.revision_id)
            if not revision or str(revision.get("campaign_id")) != campaign_id:
                raise CampaignRevisionNotFound(campaign_id)
        if not revision_id:
            latest = self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id) if self.revisions else None
            revision_id = latest.get("id") if latest else None
        if not revision_id:
            raise CampaignRevisionNotFound(campaign_id)
        self._validate_window(request.starts_at, request.ends_at)
        existing = self.schedules.get_active_by_campaign_id(campaign_id=campaign_id)
        data = {
            "campaign_id": campaign_id,
            "revision_id": str(revision_id),
            "starts_at": request.starts_at,
            "ends_at": request.ends_at,
            "timezone": request.timezone,
            "auto_unpublish": request.auto_unpublish,
            "status": "pending",
            "created_by": request.created_by,
        }
        row = self.schedules.update(schedule_id=existing["id"], data=data) if existing else self.schedules.create(data=data)
        self.campaigns.update(campaign_id=campaign_id, data={"status": "scheduled"}, team_id=self.team_id)
        return ScheduleResponse.model_validate(row)

    def update_schedule(self, campaign_id: str, request: ScheduleUpdate) -> ScheduleResponse:
        self._get_campaign(campaign_id)
        schedule = self.schedules.get_active_by_campaign_id(campaign_id=campaign_id)
        if not schedule:
            raise ScheduleNotFound(campaign_id)
        payload = request.model_dump(exclude_none=True)
        starts_at = payload.get("starts_at") or schedule.get("starts_at")
        ends_at = payload.get("ends_at") if "ends_at" in payload else schedule.get("ends_at")
        self._validate_window(starts_at, ends_at)
        row = self.schedules.update(schedule_id=schedule["id"], data=payload)
        return ScheduleResponse.model_validate(row)

    def cancel_schedule(self, campaign_id: str) -> ScheduleResponse:
        self._get_campaign(campaign_id)
        schedule = self.schedules.get_active_by_campaign_id(campaign_id=campaign_id)
        if not schedule:
            raise ScheduleNotFound(campaign_id)
        row = self.schedules.update(schedule_id=schedule["id"], data={"status": "cancelled"})
        self.campaigns.update(campaign_id=campaign_id, data={"status": "approved"}, team_id=self.team_id)
        return ScheduleResponse.model_validate(row)

    def _get_campaign(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.campaigns.get(campaign_id=campaign_id, team_id=self.team_id)
        if not campaign:
            raise CampaignNotFound(campaign_id)
        return campaign

    def _approved_campaign(self, campaign_id: str) -> dict[str, Any]:
        campaign = self._get_campaign(campaign_id)
        if campaign.get("status") not in {"approved", "scheduled"}:
            raise CampaignNotApproved(campaign_id, campaign.get("status"))
        return campaign

    @staticmethod
    def _validate_window(starts_at: str, ends_at: str | None) -> None:
        start = _parse_dt(starts_at)
        end = _parse_dt(ends_at)
        if start is None:
            raise InvalidScheduleWindow("starts_at is required")
        if end is not None and end <= start:
            raise InvalidScheduleWindow("ends_at must be after starts_at")


def _configured_service_for_team(team_id_override: str | None = None) -> ScheduleService:
    settings = Settings.from_env()
    team_id = team_id_override or settings.supabase_team_id or settings.brand_context_team_id
    if not (settings.supabase_url or settings.supabase_service_role_key or team_id):
        raise ScheduleServiceUnavailable("schedule endpoints require Supabase service-role configuration")
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return ScheduleService.from_supabase_client(client, team_id=team_id)


def configured_service() -> ScheduleService:
    return _configured_service_for_team()


def configured_service_for_team(team_id: str) -> ScheduleService:
    return _configured_service_for_team(team_id)
