from __future__ import annotations

import pytest

from app.services.shopify.publisher import CampaignNotScheduled, PublishUnsupported, ShopifyPublisher

CAMPAIGN_ID = "00000000-0000-0000-0000-000000000101"
REVISION_ID = "00000000-0000-0000-0000-000000000201"
STORE_ID = "00000000-0000-0000-0000-000000000501"
SCHEDULE_ID = "00000000-0000-0000-0000-000000000401"


class FakeShopifyClient:
    def __init__(self) -> None:
        self.assets: dict[tuple[str, str], str] = {}
        self.metafields: dict[tuple[str, str, str], str | None] = {}
        self.calls: list[tuple] = []

    def put_theme_asset(self, *, theme_id: str, key: str, value: str) -> dict:
        self.calls.append(("put_asset", theme_id, key, value))
        self.assets[(theme_id, key)] = value
        return {"key": key}

    def put_shop_metafield(self, *, namespace: str, key: str, value: str, type: str = "json") -> dict:
        self.calls.append(("put_metafield", namespace, key, value, type))
        self.metafields[("shop", namespace, key)] = value
        return {"namespace": namespace, "key": key, "value": value}

    def get_shop_metafield(self, *, namespace: str, key: str) -> dict | None:
        value = self.metafields.get(("shop", namespace, key))
        return {"namespace": namespace, "key": key, "value": value} if value is not None else None

    def delete_shop_metafield(self, *, namespace: str, key: str) -> dict:
        self.calls.append(("delete_metafield", namespace, key))
        self.metafields[("shop", namespace, key)] = None
        return {"deleted": True}


class Repo:
    def __init__(self, rows: dict[str, dict] | None = None) -> None:
        self.rows = rows or {}
        self.created: list[dict] = []

    def get(self, **kwargs):
        key = kwargs.get("campaign_id") or kwargs.get("revision_id") or kwargs.get("store_id")
        return self.rows.get(key)

    def get_active_by_campaign_id(self, *, campaign_id: str):
        return self.rows.get(campaign_id)

    def get_by_campaign_id(self, *, campaign_id: str):
        return self.rows.get(campaign_id)

    def create(self, *, data: dict):
        existing = self.get_by_idempotency_key(idempotency_key=data.get("idempotency_key")) if data.get("idempotency_key") else None
        if existing:
            return existing
        row = {"id": f"job-{len(self.created)+1}", **data}
        self.created.append(row)
        return row

    def create_or_get(self, *, data: dict):
        return self.create(data=data)

    def get_by_idempotency_key(self, *, idempotency_key: str):
        return next((row for row in self.created if row.get("idempotency_key") == idempotency_key), None)

    def update(self, *, job_id: str, data: dict):
        for row in self.created:
            if row["id"] == job_id:
                row.update(data)
                return row
        return None


class Campaigns(Repo):
    def update(self, *, campaign_id: str, data: dict, team_id: str | None = None):
        self.rows[campaign_id].update(data)
        return self.rows[campaign_id]


def _publisher(status: str = "scheduled", target_type: str = "home") -> tuple[ShopifyPublisher, FakeShopifyClient, Repo, Campaigns]:
    client = FakeShopifyClient()
    jobs = Repo()
    campaigns = Campaigns({CAMPAIGN_ID: {"id": CAMPAIGN_ID, "store_id": STORE_ID, "status": status, "selected_revision_id": REVISION_ID, "title": "Summer"}})
    revisions = Repo({REVISION_ID: {"id": REVISION_ID, "campaign_id": CAMPAIGN_ID, "liquid_config": {"slug": "summer", "variants": []}}})
    stores = Repo({STORE_ID: {"id": STORE_ID, "theme_id": "123", "banner_metafield_namespace": "aijolot", "banner_metafield_key": "banner_campaigns"}})
    schedules = Repo({CAMPAIGN_ID: {"id": SCHEDULE_ID, "campaign_id": CAMPAIGN_ID, "revision_id": REVISION_ID, "starts_at": "2026-06-10T10:00:00Z", "ends_at": "2026-06-12T10:00:00Z", "status": "pending"}})
    placements = Repo({CAMPAIGN_ID: {"campaign_id": CAMPAIGN_ID, "target_type": target_type, "slot": "hero"}})
    publisher = ShopifyPublisher(
        client=client,
        campaigns=campaigns,
        revisions=revisions,
        stores=stores,
        schedules=schedules,
        placements=placements,
        publish_jobs=jobs,
    )
    return publisher, client, jobs, campaigns


def test_install_theme_files_is_idempotent() -> None:
    publisher, client, jobs, _ = _publisher()

    first = publisher.install_theme_files(STORE_ID)
    second = publisher.install_theme_files(STORE_ID)

    assert first.status == "succeeded"
    assert second.status == "succeeded"
    asset_calls = [call for call in client.calls if call[0] == "put_asset"]
    assert [call[2] for call in asset_calls[:2]] == ["sections/aijolot-banner-agent.liquid", "snippets/aijolot-banner-agent-block.liquid"]
    assert first.id == second.id
    assert len(jobs.created) == 0


def test_publish_writes_config_metafield_and_records_job() -> None:
    publisher, client, jobs, campaigns = _publisher()

    result = publisher.publish_campaign(CAMPAIGN_ID)

    assert result.status == "succeeded"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "published"
    assert client.metafields[("shop", "aijolot", "banner_campaigns")]
    payload = jobs.created[-1]["request_payload"]
    assert payload["campaign_id"] == CAMPAIGN_ID
    assert payload["config"]["active_from"] == "2026-06-10T10:00:00Z"
    assert payload["config"]["active_until"] == "2026-06-12T10:00:00Z"


def test_unpublish_clears_config_and_records_job() -> None:
    publisher, client, jobs, campaigns = _publisher(status="published")

    result = publisher.unpublish_campaign(CAMPAIGN_ID)
    repeat = publisher.unpublish_campaign(CAMPAIGN_ID)

    assert result.action == "unpublish"
    assert result.status == "succeeded"
    assert repeat.id == result.id
    assert client.metafields[("shop", "aijolot", "banner_campaigns")] == "[]"
    assert jobs.created[-1]["action"] == "unpublish"
    assert len(jobs.created) == 1
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "approved"


def test_publish_requires_scheduled_state() -> None:
    publisher, _, _, _ = _publisher(status="needs_review")

    with pytest.raises(CampaignNotScheduled):
        publisher.publish_campaign(CAMPAIGN_ID)

    approved_without_schedule, _, _, _ = _publisher(status="approved")
    approved_without_schedule.schedules.rows.clear()

    with pytest.raises(CampaignNotScheduled, match="must be scheduled"):
        approved_without_schedule.publish_campaign(CAMPAIGN_ID)


def test_publish_is_idempotent_for_already_published_campaign() -> None:
    publisher, client, jobs, _ = _publisher(status="published")

    first = publisher.publish_campaign(CAMPAIGN_ID)
    second = publisher.publish_campaign(CAMPAIGN_ID)

    assert first.status == "succeeded"
    assert second.id == first.id
    assert len(jobs.created) == 1
    assert len([call for call in client.calls if call[0] == "put_metafield"]) == 1


def test_unpublish_requires_published_or_scheduled_campaign() -> None:
    publisher, _, _, _ = _publisher(status="needs_review")

    with pytest.raises(CampaignNotScheduled):
        publisher.unpublish_campaign(CAMPAIGN_ID)


def test_search_result_placement_returns_clear_unsupported_error() -> None:
    publisher, _, _, _ = _publisher(target_type="search")

    with pytest.raises(PublishUnsupported, match="search result placement"):
        publisher.publish_campaign(CAMPAIGN_ID)
