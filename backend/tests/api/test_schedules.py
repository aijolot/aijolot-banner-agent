from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.banners.schedule_service import ScheduleService
from tests.unit.test_schedule_service import CAMPAIGN_ID, InMemoryCampaigns, InMemorySchedules

client = TestClient(app)


def _install(monkeypatch, status: str = "approved"):
    from app.api.v1 import schedules

    campaigns = InMemoryCampaigns(status)
    repo = InMemorySchedules()
    service = ScheduleService(campaigns=campaigns, revisions=None, schedules=repo)
    monkeypatch.setattr(schedules, "_schedule_service", lambda: service)
    return service, campaigns, repo


def test_schedule_patch_and_cancel_campaign(monkeypatch) -> None:
    _, campaigns, _ = _install(monkeypatch)

    created = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/schedule",
        json={"starts_at": "2026-06-10T10:00:00Z", "ends_at": "2026-06-12T10:00:00Z", "timezone": "UTC"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["campaign_id"] == CAMPAIGN_ID
    assert created.json()["revision_id"] == campaigns.rows[CAMPAIGN_ID]["selected_revision_id"]
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "scheduled"

    patched = client.patch(f"/api/v1/campaigns/{CAMPAIGN_ID}/schedule", json={"ends_at": "2026-06-13T10:00:00Z"})
    cancelled = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/schedule/cancel")

    assert patched.status_code == 200, patched.text
    assert patched.json()["ends_at"] == "2026-06-13T10:00:00Z"
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"


def test_schedule_endpoint_errors(monkeypatch) -> None:
    _install(monkeypatch, status="needs_review")
    denied = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/schedule", json={"starts_at": "2026-06-10T10:00:00Z"})
    assert denied.status_code == 409

    _install(monkeypatch, status="approved")
    invalid = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/schedule", json={"starts_at": "2026-06-10T10:00:00Z", "ends_at": "2026-06-09T10:00:00Z"})
    missing_schedule = client.patch(f"/api/v1/campaigns/{CAMPAIGN_ID}/schedule", json={"timezone": "UTC"})
    assert invalid.status_code == 422
    assert missing_schedule.status_code == 404


def test_default_schedule_endpoint_returns_503(monkeypatch) -> None:
    from app.api.v1 import schedules
    from app.services.banners.schedule_service import configured_service

    monkeypatch.setattr(schedules, "_schedule_service", configured_service)
    response = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/schedule", json={"starts_at": "2026-06-10T10:00:00Z"})

    assert response.status_code == 503
