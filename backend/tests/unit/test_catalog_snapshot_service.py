from __future__ import annotations

import pytest

from app.schemas.stores import ShopifyResourceSummary
from app.services.banners.catalog_snapshot_service import (
    CampaignCatalogSnapshotNotFound,
    CampaignNotFound,
    CatalogSnapshotService,
)

CAMPAIGN_ID = "00000000-0000-0000-0000-000000000301"
TEAM_ID = "team-1"
STORE_ID = "00000000-0000-0000-0000-000000000101"


class FakeCampaignRepository:
    def __init__(self) -> None:
        self.rows = {
            CAMPAIGN_ID: {"id": CAMPAIGN_ID, "team_id": TEAM_ID, "store_id": STORE_ID, "title": "Promo"}
        }

    def get(self, *, campaign_id: str, team_id: str | None = None):
        row = self.rows.get(campaign_id)
        if row and (team_id is None or row["team_id"] == team_id):
            return row
        return None


class FakeCatalogRepository:
    def __init__(self) -> None:
        self.saved: dict[str, object] | None = None

    def create_snapshot(self, *, campaign_id: str, source: str, query_summary: str | None, discount_rule: dict, items: list[dict]):
        self.saved = {
            "campaign_id": campaign_id,
            "source": source,
            "query_summary": query_summary,
            "discount_rule": discount_rule,
            "items": items,
        }
        return {"id": "snap-1", "campaign_id": campaign_id, "source": source, "query_summary": query_summary, "discount_rule": discount_rule, "items": items, "created_at": "2026-05-30T00:00:00Z"}

    def get_latest_by_campaign_id(self, *, campaign_id: str):
        if self.saved and self.saved["campaign_id"] == campaign_id:
            return {"id": "snap-1", "campaign_id": campaign_id, "source": "shopify_resource_cache", "query_summary": self.saved["query_summary"], "discount_rule": self.saved["discount_rule"], "items": self.saved["items"], "created_at": "2026-05-30T00:00:00Z"}
        return None


class FakeResourceService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def list_resources(self, store_id: str, *, resource_type: str, limit: int = 100):
        self.calls.append((store_id, resource_type, limit))
        assert store_id == STORE_ID
        if resource_type == "product":
            return [
                ShopifyResourceSummary(
                    id="res-1",
                    store_id=STORE_ID,
                    resource_type="product",
                    shopify_gid="gid://shopify/Product/1",
                    handle="hero-product",
                    title="Hero Product",
                    vendor="Vendor",
                    tags=["vip"],
                    image_url="https://cdn.example/hero.png",
                    status="active",
                    metadata={"sku": "SKU-1", "price": 12.5, "sale": 10, "stock": 7, "secret_token": "drop"},
                )
            ]
        return []


def test_create_snapshot_uses_campaign_store_and_cache_resources() -> None:
    catalog_repo = FakeCatalogRepository()
    resource_service = FakeResourceService()
    service = CatalogSnapshotService(
        campaign_repository=FakeCampaignRepository(),
        catalog_repository=catalog_repo,
        resource_service=resource_service,
        team_id=TEAM_ID,
    )

    snapshot = service.create_snapshot(CAMPAIGN_ID, query_summary="VIP products", discount_rule={"pct": 20})

    assert resource_service.calls == [(STORE_ID, "product", 100)]
    assert snapshot.id == "snap-1"
    assert snapshot.campaign_id == CAMPAIGN_ID
    assert snapshot.source == "shopify_resource_cache"
    assert snapshot.item_count == 1
    item = snapshot.items[0]
    assert item.shopify_product_gid == "gid://shopify/Product/1"
    assert item.handle == "hero-product"
    assert item.vendor == "Vendor"
    assert item.sku == "SKU-1"
    assert item.price == 12.5
    assert item.sale_price == 10
    assert item.stock == 7
    assert "secret_token" not in item.raw["metadata"]
    assert snapshot.store_id == STORE_ID


def test_create_snapshot_validates_configured_campaign_team() -> None:
    service = CatalogSnapshotService(
        campaign_repository=FakeCampaignRepository(),
        catalog_repository=FakeCatalogRepository(),
        resource_service=FakeResourceService(),
        team_id="other-team",
    )

    with pytest.raises(CampaignNotFound):
        service.create_snapshot(CAMPAIGN_ID)


def test_local_mode_persists_snapshot_in_memory() -> None:
    service = CatalogSnapshotService(resource_service=FakeResourceService())

    created = service.create_snapshot(CAMPAIGN_ID, store_id=STORE_ID, limit=5)
    fetched = service.get_snapshot(CAMPAIGN_ID)

    assert created.id == fetched.id
    assert fetched.item_count == 1
    assert fetched.store_id == STORE_ID


def test_get_snapshot_preserves_original_store_id_if_campaign_changes() -> None:
    campaign_repo = FakeCampaignRepository()
    service = CatalogSnapshotService(
        campaign_repository=campaign_repo,
        catalog_repository=FakeCatalogRepository(),
        resource_service=FakeResourceService(),
        team_id=TEAM_ID,
    )

    created = service.create_snapshot(CAMPAIGN_ID)
    campaign_repo.rows[CAMPAIGN_ID]["store_id"] = "00000000-0000-0000-0000-000000000102"
    fetched = service.get_snapshot(CAMPAIGN_ID)

    assert created.store_id == STORE_ID
    assert fetched.store_id == STORE_ID


def test_get_missing_snapshot_raises_not_found() -> None:
    service = CatalogSnapshotService(resource_service=FakeResourceService())

    with pytest.raises(CampaignCatalogSnapshotNotFound):
        service.get_snapshot("00000000-0000-0000-0000-000000000399")
