from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.banners.usage_guard_service import InMemoryUsageEventStore, UsageGuardService


class RecordingRepository:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        self.rows.append(dict(data))
        return dict(data)

    def count_since(self, *, user_id: str, event_type: str, since: datetime) -> int:
        return sum(
            1
            for row in self.rows
            if row["user_id"] == user_id
            and row["event_type"] == event_type
            and row["created_at"] >= since
        )


def test_usage_guard_warns_on_twentieth_image_generation_in_15_minutes():
    service = UsageGuardService(limit=20)
    now = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)

    result = None
    for index in range(20):
        result = service.record_image_generation(user_id="user-1", now=now + timedelta(seconds=index))

    assert result is not None
    assert result.count == 20
    assert result.warning is True
    assert result.limit == 20
    assert "20 image generations" in (result.message or "")
    assert result.to_metadata()["warning"] is True


def test_usage_guard_does_not_warn_before_threshold_and_is_per_user():
    service = UsageGuardService(limit=20)
    now = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)

    for index in range(19):
        result = service.record_image_generation(user_id="user-1", now=now + timedelta(seconds=index))
        assert result.warning is False

    other = service.record_image_generation(user_id="user-2", now=now + timedelta(minutes=1))
    assert other.count == 1
    assert other.warning is False


def test_usage_guard_window_resets_outside_15_minutes():
    service = UsageGuardService(limit=20)
    base = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)

    result = None
    for index in range(20):
        result = service.record_image_generation(user_id="user-1", now=base + timedelta(seconds=index))
    assert result is not None
    assert result.warning is True

    reset = service.record_image_generation(user_id="user-1", now=base + timedelta(minutes=16))
    assert reset.count == 1
    assert reset.warning is False


def test_usage_guard_uses_repository_when_team_id_is_available():
    repo = RecordingRepository()
    service = UsageGuardService(repository=repo, limit=2)
    now = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)

    user_id = "11111111-1111-1111-1111-111111111111"
    team_id = "22222222-2222-2222-2222-222222222222"
    campaign_id = "33333333-3333-3333-3333-333333333333"
    first = service.record_image_generation(
        user_id=user_id,
        team_id=team_id,
        campaign_id=campaign_id,
        provider="fake",
        model="fake-nano-banana-v1",
        estimated_cost_usd=0.0,
        metadata={"size_bytes": 123},
        now=now,
    )
    second = service.record_image_generation(user_id=user_id, team_id=team_id, now=now + timedelta(seconds=1))

    assert first.warning is False
    assert second.count == 2
    assert second.warning is True
    assert len(repo.rows) == 2
    assert repo.rows[0]["team_id"] == team_id
    assert repo.rows[0]["campaign_id"] == campaign_id
    assert repo.rows[0]["user_id"] == user_id
    assert repo.rows[0]["event_type"] == "image_generation"
    assert repo.rows[0]["provider"] == "fake"


def test_usage_guard_falls_back_to_memory_without_team_id_even_with_repository():
    repo = RecordingRepository()
    service = UsageGuardService(repository=repo, limit=1)
    now = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)

    result = service.record_image_generation(user_id="11111111-1111-1111-1111-111111111111", now=now)

    assert result.warning is True
    assert result.count == 1
    assert repo.rows == []


def test_usage_guard_falls_back_to_memory_without_profile_uuid_even_with_team_id():
    repo = RecordingRepository()
    service = UsageGuardService(repository=repo, limit=1)
    now = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)

    result = service.record_image_generation(user_id=None, team_id="22222222-2222-2222-2222-222222222222", now=now)

    assert result.user_id == "anonymous"
    assert result.warning is True
    assert result.count == 1
    assert repo.rows == []


def test_usage_guard_falls_back_to_memory_without_uuid_team_id_or_campaign_id():
    repo = RecordingRepository()
    service = UsageGuardService(repository=repo, limit=2)
    now = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)
    user_id = "11111111-1111-1111-1111-111111111111"

    invalid_team = service.record_image_generation(user_id=user_id, team_id="team-1", now=now)
    invalid_campaign = service.record_image_generation(
        user_id=user_id,
        team_id="22222222-2222-2222-2222-222222222222",
        campaign_id="campaign-1",
        now=now + timedelta(seconds=1),
    )

    assert invalid_team.count == 1
    assert invalid_campaign.count == 2
    assert invalid_campaign.warning is True
    assert repo.rows == []


def test_usage_guard_includes_events_at_exact_window_boundary():
    service = UsageGuardService(limit=2)
    base = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)

    service.record_image_generation(user_id="user-1", now=base)
    boundary = service.record_image_generation(user_id="user-1", now=base + timedelta(minutes=15))

    assert boundary.count == 2
    assert boundary.warning is True


def test_in_memory_store_can_be_shared_and_cleared():
    store = InMemoryUsageEventStore()
    service = UsageGuardService(memory_store=store, limit=1)
    now = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)

    assert service.record_image_generation(user_id="anonymous", now=now).warning is True
    store.clear()
    assert store.count_since(user_id="anonymous", event_type="image_generation", since=now - timedelta(minutes=15)) == 0
