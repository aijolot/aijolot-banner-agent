from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.settings import Settings
from app.db.repositories.campaign_messages import CampaignMessageRepository
from app.db.repositories.campaigns import CampaignRepository
from app.services.supabase.client import SupabaseClientFactory

pytestmark = pytest.mark.integration


class _FakeTable:
    def __init__(self) -> None:
        self.payload: dict | None = None

    def insert(self, payload: dict):
        self.payload = payload
        return self


class _FakeClient:
    def __init__(self) -> None:
        self.table_obj = _FakeTable()

    def table(self, name: str) -> _FakeTable:
        assert name == "campaigns"
        return self.table_obj


def test_campaign_repository_create_filters_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.db.repositories.campaigns as module

    fake_client = _FakeClient()

    def fake_execute_data(query):
        assert query is fake_client.table_obj
        assert fake_client.table_obj.payload is not None
        return {**fake_client.table_obj.payload, "id": "11111111-1111-1111-1111-111111111111"}

    monkeypatch.setattr(module, "execute_data", fake_execute_data)

    row = CampaignRepository(fake_client).create(  # type: ignore[arg-type]
        team_id="00000000-0000-0000-0000-000000000001",
        store_id="00000000-0000-0000-0000-000000000002",
        title="Pytest Campaign",
        raw_brief="raw",
        structured_brief={"goal": "sale"},
    )

    assert row["id"] == "11111111-1111-1111-1111-111111111111"
    assert row["team_id"] == "00000000-0000-0000-0000-000000000001"
    assert row["store_id"] == "00000000-0000-0000-0000-000000000002"
    assert row["structured_brief"] == {"goal": "sale"}
    assert "messages" not in row


def _client_team_store():
    if os.getenv("RUN_LIVE_SUPABASE_TESTS") != "1":
        pytest.skip("set RUN_LIVE_SUPABASE_TESTS=1 to run live Supabase integration tests")
    settings = Settings.from_env()
    team_id = os.getenv("SUPABASE_TEAM_ID")
    store_id = os.getenv("SUPABASE_STORE_ID")
    if settings.supabase_url is None or settings.supabase_service_role_key is None or not team_id:
        pytest.skip("Supabase service-role settings and SUPABASE_TEAM_ID are required")
    try:
        client = SupabaseClientFactory(settings).service_role_client()
        repo = CampaignRepository(client)
        store_id = store_id or repo.first_store_id(team_id=team_id)
        if not store_id:
            pytest.skip("SUPABASE_STORE_ID or an existing team store is required")
        client.table("teams").select("id").eq("id", team_id).limit(1).execute()
    except Exception as exc:  # noqa: BLE001 - live integration availability check
        pytest.skip(f"Supabase is not available: {exc}")
    return client, team_id, store_id


def test_campaign_repository_roundtrip_live_supabase() -> None:
    client, team_id, store_id = _client_team_store()
    campaigns = CampaignRepository(client)
    messages = CampaignMessageRepository(client)
    title = f"Pytest Campaign {uuid4().hex[:8]}"

    created = campaigns.create(
        team_id=team_id,
        store_id=store_id,
        title=title,
        raw_brief="Black Friday",
        structured_brief={"goal": "Black Friday"},
    )
    campaign_id = created["id"]
    try:
        messages.create(campaign_id=campaign_id, author_type="user", body="Black Friday")
        loaded = campaigns.get(campaign_id=campaign_id, team_id=team_id)
        assert loaded is not None
        assert loaded["title"] == title
        assert loaded["structured_brief"]["goal"] == "Black Friday"
        assert any(row["body"] == "Black Friday" for row in messages.list_for_campaign(campaign_id=campaign_id))

        patched = campaigns.update(campaign_id=campaign_id, team_id=team_id, data={"status": "needs_review"})
        assert patched is not None
        assert patched["status"] == "needs_review"
    finally:
        campaigns.update(campaign_id=campaign_id, team_id=team_id, data={"archived_at": datetime.now(UTC).isoformat()})
