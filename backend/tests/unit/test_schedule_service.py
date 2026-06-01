from __future__ import annotations

import pytest

from app.schemas.schedules import ScheduleCreate, ScheduleUpdate
from app.services.banners.schedule_service import CampaignNotApproved, CampaignNotFound, InvalidScheduleWindow, ScheduleNotFound, ScheduleService

CAMPAIGN_ID = "00000000-0000-0000-0000-000000000101"
REVISION_ID = "00000000-0000-0000-0000-000000000201"
USER_ID = "00000000-0000-0000-0000-000000000301"


class InMemoryCampaigns:
    def __init__(self, status: str = "approved") -> None:
        self.rows = {CAMPAIGN_ID: {"id": CAMPAIGN_ID, "status": status, "selected_revision_id": REVISION_ID}}

    def get(self, *, campaign_id: str, team_id: str | None = None):
        return self.rows.get(campaign_id)

    def update(self, *, campaign_id: str, data: dict, team_id: str | None = None):
        if campaign_id not in self.rows:
            return None
        self.rows[campaign_id].update(data)
        return self.rows[campaign_id]


class InMemorySchedules:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.next_id = "00000000-0000-0000-0000-000000000401"

    def get_active_by_campaign_id(self, *, campaign_id: str):
        return next((row for row in self.rows.values() if row["campaign_id"] == campaign_id and row["status"] != "cancelled"), None)

    def create(self, *, data: dict):
        row = {"id": self.next_id, "status": "pending", **data}
        self.rows[row["id"]] = row
        return row

    def update(self, *, schedule_id: str, data: dict):
        row = self.rows.get(schedule_id)
        if not row:
            return None
        row.update(data)
        return row


def _service(status: str = "approved") -> tuple[ScheduleService, InMemoryCampaigns, InMemorySchedules]:
    campaigns = InMemoryCampaigns(status)
    schedules = InMemorySchedules()
    return ScheduleService(campaigns=campaigns, revisions=None, schedules=schedules), campaigns, schedules


def test_schedule_approved_campaign_transitions_to_scheduled() -> None:
    service, campaigns, schedules = _service()

    result = service.schedule_campaign(
        CAMPAIGN_ID,
        ScheduleCreate(starts_at="2026-06-10T10:00:00Z", ends_at="2026-06-12T10:00:00Z", timezone="Asia/Bishkek", created_by=USER_ID),
    )

    assert result.campaign_id == CAMPAIGN_ID
    assert result.revision_id == REVISION_ID
    assert result.status == "pending"
    assert result.timezone == "Asia/Bishkek"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "scheduled"
    assert schedules.rows[result.id]["created_by"] == USER_ID


def test_schedule_rejects_unapproved_or_missing_campaign() -> None:
    service, _, _ = _service("needs_review")

    with pytest.raises(CampaignNotApproved):
        service.schedule_campaign(CAMPAIGN_ID, ScheduleCreate(starts_at="2026-06-10T10:00:00Z"))
    with pytest.raises(CampaignNotFound):
        service.schedule_campaign("00000000-0000-0000-0000-000000000999", ScheduleCreate(starts_at="2026-06-10T10:00:00Z"))


def test_schedule_requires_end_after_start() -> None:
    service, _, _ = _service()

    with pytest.raises(InvalidScheduleWindow):
        service.schedule_campaign(CAMPAIGN_ID, ScheduleCreate(starts_at="2026-06-10T10:00:00Z", ends_at="2026-06-09T10:00:00Z"))


def test_patch_schedule_and_cancel() -> None:
    service, campaigns, _ = _service()
    created = service.schedule_campaign(CAMPAIGN_ID, ScheduleCreate(starts_at="2026-06-10T10:00:00Z"))

    patched = service.update_schedule(CAMPAIGN_ID, ScheduleUpdate(ends_at="2026-06-11T10:00:00Z", auto_unpublish=False))
    cancelled = service.cancel_schedule(CAMPAIGN_ID)

    assert patched.id == created.id
    assert patched.ends_at == "2026-06-11T10:00:00Z"
    assert patched.auto_unpublish is False
    assert cancelled.status == "cancelled"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "approved"


def test_update_missing_schedule_fails() -> None:
    service, _, _ = _service()

    with pytest.raises(ScheduleNotFound):
        service.update_schedule(CAMPAIGN_ID, ScheduleUpdate(timezone="UTC"))
