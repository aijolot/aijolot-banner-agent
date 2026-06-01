from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.stores import ShopifyResourceSummary, StoreSummary

client = TestClient(app)
AUTH_HEADERS = {"X-Aijolot-User-Id": "test-user", "X-Aijolot-Team-Id": "00000000-0000-0000-0000-000000000001", "X-Aijolot-Store-Id": "00000000-0000-0000-0000-000000000101"}
STORE_ID = "00000000-0000-0000-0000-000000000101"


class FakeStoreService:
    def list_stores(self):
        return [
            StoreSummary(
                id=STORE_ID,
                team_id="team-1",
                shop_domain="demo.myshopify.com",
                name="Demo Store",
                shopify_api_version="2026-01",
                theme_id="theme-1",
                status="connected",
            )
        ]

    def get_store(self, store_id: str):
        if store_id == STORE_ID:
            return self.list_stores()[0]
        from app.services.shopify.resource_service import StoreNotFound

        raise StoreNotFound(store_id)

    def list_resources(self, store_id: str, *, resource_type: str):
        if store_id != STORE_ID:
            from app.services.shopify.resource_service import StoreNotFound

            raise StoreNotFound(store_id)
        return [
            ShopifyResourceSummary(
                id="resource-1",
                store_id=store_id,
                resource_type=resource_type,
                shopify_gid="gid://shopify/Product/1" if resource_type != "search" else None,
                handle="demo-product" if resource_type != "search" else "search",
                title="Demo Product" if resource_type != "search" else "Search results",
                vendor="Demo Vendor" if resource_type == "product" else None,
                tags=["demo"],
                image_url=None,
                status="active",
                metadata={"sku": "SKU-1"} if resource_type == "product" else {},
            )
        ]


def test_list_stores(monkeypatch) -> None:
    from app.api.v1 import stores

    monkeypatch.setattr(stores, "_default_service", lambda: FakeStoreService())

    response = client.get("/api/v1/stores", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": STORE_ID,
            "team_id": "team-1",
            "shop_domain": "demo.myshopify.com",
            "name": "Demo Store",
            "shopify_api_version": "2026-01",
            "theme_id": "theme-1",
            "status": "connected",
            "banner_metafield_namespace": "aijolot",
            "banner_metafield_key": "banner_campaigns",
        }
    ]
    assert "access_token" not in response.text


def test_get_store(monkeypatch) -> None:
    from app.api.v1 import stores

    monkeypatch.setattr(stores, "_default_service", lambda: FakeStoreService())

    response = client.get(f"/api/v1/stores/{STORE_ID}", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["id"] == STORE_ID


def test_get_store_404(monkeypatch) -> None:
    from app.api.v1 import stores

    monkeypatch.setattr(stores, "_default_service", lambda: FakeStoreService())

    response = client.get("/api/v1/stores/00000000-0000-0000-0000-000000000999", headers=AUTH_HEADERS)

    assert response.status_code == 404


def test_list_shopify_resources(monkeypatch) -> None:
    from app.api.v1 import stores

    monkeypatch.setattr(stores, "_default_service", lambda: FakeStoreService())

    response = client.get(f"/api/v1/stores/{STORE_ID}/shopify/resources?resource_type=product", headers=AUTH_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body[0]["resource_type"] == "product"
    assert body[0]["metadata"] == {"sku": "SKU-1"}


def test_search_is_valid_resource_type(monkeypatch) -> None:
    from app.api.v1 import stores

    monkeypatch.setattr(stores, "_default_service", lambda: FakeStoreService())

    response = client.get(f"/api/v1/stores/{STORE_ID}/shopify/resources?resource_type=search", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()[0]["resource_type"] == "search"


def test_invalid_resource_type_returns_422(monkeypatch) -> None:
    from app.api.v1 import stores

    monkeypatch.setattr(stores, "_default_service", lambda: FakeStoreService())

    response = client.get(f"/api/v1/stores/{STORE_ID}/shopify/resources?resource_type=blog", headers=AUTH_HEADERS)

    assert response.status_code == 422


def test_invalid_store_id_returns_422(monkeypatch) -> None:
    from app.api.v1 import stores

    monkeypatch.setattr(stores, "_default_service", lambda: FakeStoreService())

    assert client.get("/api/v1/stores/not-a-uuid").status_code == 422


def test_store_routes_appear_in_openapi(monkeypatch) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/stores" in paths
    assert "/api/v1/stores/{store_id}" in paths
    assert "/api/v1/stores/{store_id}/shopify/resources" in paths
