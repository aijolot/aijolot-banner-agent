from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.catalog import CatalogSnapshotResponse

client = TestClient(app)
CAMPAIGN_ID = "00000000-0000-0000-0000-000000000301"
STORE_ID = "00000000-0000-0000-0000-000000000101"
AUTH_HEADERS = {"X-Aijolot-User-Id": "test-user", "X-Aijolot-Team-Id": "test-team", "X-Aijolot-Store-Id": "test-store"}


class FakeCatalogSnapshotService:
    def __init__(self) -> None:
        self.saved: CatalogSnapshotResponse | None = None

    def create_snapshot(self, campaign_id: str, *, store_id: str | None = None, query_summary: str | None = None, discount_rule=None, resource_types=None, limit: int = 100):
        if campaign_id.endswith("999"):
            from app.services.banners.catalog_snapshot_service import CampaignNotFound

            raise CampaignNotFound(campaign_id)
        self.saved = CatalogSnapshotResponse(
            id="snap-1",
            campaign_id=campaign_id,
            store_id=store_id or STORE_ID,
            source="shopify_resource_cache",
            query_summary=query_summary,
            discount_rule=discount_rule or {},
            items=[
                {
                    "id": "item-1",
                    "resource_type": "product",
                    "shopify_product_gid": "gid://shopify/Product/1",
                    "handle": "hero-product",
                    "title": "Hero Product",
                    "vendor": "Vendor",
                    "tags": ["vip"],
                    "sku": "SKU-1",
                    "price": 12.5,
                    "sale_price": 10,
                    "stock": 7,
                    "image_url": "https://cdn.example/hero.png",
                    "raw": {"status": "active"},
                }
            ],
            item_count=1,
            created_at="2026-05-30T00:00:00Z",
        )
        return self.saved

    def get_snapshot(self, campaign_id: str):
        if self.saved and self.saved.campaign_id == campaign_id:
            return self.saved
        from app.services.banners.catalog_snapshot_service import CampaignCatalogSnapshotNotFound

        raise CampaignCatalogSnapshotNotFound(campaign_id)


def test_create_and_get_catalog_snapshot(monkeypatch) -> None:
    from app.api.v1 import catalog

    fake = FakeCatalogSnapshotService()
    monkeypatch.setattr(catalog, "_default_service", lambda: fake)

    post = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/catalog-snapshot",
        headers=AUTH_HEADERS,
        json={"store_id": STORE_ID, "query_summary": "VIP products", "discount_rule": {"pct": 20}},
    )
    get = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/catalog-snapshot", headers=AUTH_HEADERS)

    assert post.status_code == 200
    assert post.json()["campaign_id"] == CAMPAIGN_ID
    assert post.json()["source"] == "shopify_resource_cache"
    assert post.json()["item_count"] == 1
    assert post.json()["items"][0]["sku"] == "SKU-1"
    assert get.status_code == 200
    assert get.json()["id"] == "snap-1"


def test_create_snapshot_unknown_campaign_returns_404(monkeypatch) -> None:
    from app.api.v1 import catalog

    monkeypatch.setattr(catalog, "_default_service", lambda: FakeCatalogSnapshotService())

    response = client.post(
        "/api/v1/campaigns/00000000-0000-0000-0000-000000000999/catalog-snapshot",
        headers=AUTH_HEADERS,
        json={"store_id": STORE_ID},
    )

    assert response.status_code == 404


def test_get_missing_snapshot_returns_404(monkeypatch) -> None:
    from app.api.v1 import catalog

    monkeypatch.setattr(catalog, "_default_service", lambda: FakeCatalogSnapshotService())

    response = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/catalog-snapshot", headers=AUTH_HEADERS)

    assert response.status_code == 404


def test_catalog_snapshot_validation_errors(monkeypatch) -> None:
    from app.api.v1 import catalog

    monkeypatch.setattr(catalog, "_default_service", lambda: FakeCatalogSnapshotService())

    assert client.get("/api/v1/campaigns/not-a-uuid/catalog-snapshot").status_code == 422
    response = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/catalog-snapshot",
        json={"store_id": "not-a-uuid"},
    )
    assert response.status_code == 422
