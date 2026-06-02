from __future__ import annotations

import pytest

from app.core.settings import MissingSettingsError
from app.services.shopify.resource_service import ShopifyResourceService, StoreNotFound

STORE_ID = "00000000-0000-0000-0000-000000000101"


class FakeStoreRepository:
    def __init__(self) -> None:
        self.rows = [
            {
                "id": STORE_ID,
                "team_id": "team-1",
                "shop_domain": "demo.myshopify.com",
                "display_name": "Demo Store",
                "access_token_secret_ref": "secret/ref",
                "encrypted_access_token": "ciphertext",
                "shopify_api_version": "2026-01",
                "theme_id": "theme-1",
                "banner_metafield_namespace": "aijolot",
                "banner_metafield_key": "banner_campaigns",
                "status": "connected",
                "created_at": "2026-05-01T00:00:00Z",
                "updated_at": "2026-05-02T00:00:00Z",
            }
        ]

    def list(self, *, team_id: str | None = None, limit: int = 100):
        return [row for row in self.rows if team_id is None or row["team_id"] == team_id][:limit]

    def get(self, *, store_id: str, team_id: str | None = None):
        return next((row for row in self.rows if row["id"] == store_id and (team_id is None or row["team_id"] == team_id)), None)


class FakeResourceRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.rows = [
            {
                "id": "res-2",
                "store_id": STORE_ID,
                "resource_type": "product",
                "shopify_gid": "gid://shopify/Product/2",
                "handle": "z-product",
                "title": "Z Product",
                "vendor": "Vendor",
                "tags": ["vip"],
                "image_url": "https://cdn.example/z.png",
                "status": "active",
                "raw": {"sku": "SKU-Z", "price": 10, "sale": 8, "stock": 5},
                "synced_at": "2026-05-03T00:00:00Z",
            },
            {
                "id": "res-1",
                "store_id": STORE_ID,
                "resource_type": "product",
                "shopify_gid": "gid://shopify/Product/1",
                "handle": "a-product",
                "title": "A Product",
                "vendor": "Vendor",
                "tags": [],
                "image_url": None,
                "status": "active",
                "raw": {
                    "access_token": "must-not-leak",
                    "secret_key": "must-not-leak",
                    "headers": {"Authorization": "must-not-leak"},
                    "credentials": {"token": "must-not-leak", "public": "ok"},
                },
                "synced_at": "2026-05-03T00:00:00Z",
            },
        ]

    def list_for_store(self, *, store_id: str, resource_type: str, limit: int = 100):
        self.calls.append((store_id, resource_type, limit))
        return [row for row in self.rows if row["store_id"] == store_id and row["resource_type"] == resource_type][:limit]


def test_list_stores_sanitizes_secret_fields() -> None:
    service = ShopifyResourceService(store_repository=FakeStoreRepository(), resource_repository=FakeResourceRepository())

    stores = service.list_stores()

    assert len(stores) == 1
    body = stores[0].model_dump()
    assert body["id"] == STORE_ID
    assert body["name"] == "Demo Store"
    assert body["shop_domain"] == "demo.myshopify.com"
    assert "access_token_secret_ref" not in body
    assert "encrypted_access_token" not in body


def test_team_scope_filters_stores() -> None:
    service = ShopifyResourceService(
        store_repository=FakeStoreRepository(),
        resource_repository=FakeResourceRepository(),
        team_id="other-team",
    )

    assert service.list_stores() == []
    with pytest.raises(StoreNotFound):
        service.get_store(STORE_ID)


def test_get_resources_uses_cache_repository_only_and_sorts_by_title() -> None:
    resource_repo = FakeResourceRepository()
    service = ShopifyResourceService(store_repository=FakeStoreRepository(), resource_repository=resource_repo)

    resources = service.list_resources(STORE_ID, resource_type="product")

    assert resource_repo.calls == [(STORE_ID, "product", 100)]
    assert [item.title for item in resources] == ["A Product", "Z Product"]
    assert resources[1].metadata["sku"] == "SKU-Z"
    assert resources[1].metadata["price"] == 10
    assert "access_token" not in resources[0].metadata
    assert "secret_key" not in resources[0].metadata
    assert "Authorization" not in resources[0].metadata.get("headers", {})
    assert "token" not in resources[0].metadata.get("credentials", {})
    assert resources[0].metadata["credentials"] == {"public": "ok"}


def test_search_resource_type_returns_virtual_resource_without_cache_call() -> None:
    resource_repo = FakeResourceRepository()
    service = ShopifyResourceService(store_repository=FakeStoreRepository(), resource_repository=resource_repo)

    resources = service.list_resources(STORE_ID, resource_type="search")

    assert resource_repo.calls == []
    assert resources[0].resource_type == "search"
    assert resources[0].handle == "search"
    assert resources[0].shopify_gid is None


def test_missing_store_raises_not_found() -> None:
    service = ShopifyResourceService(store_repository=FakeStoreRepository(), resource_repository=FakeResourceRepository())

    with pytest.raises(StoreNotFound):
        service.get_store("missing")


def test_configured_service_fails_closed_when_supabase_has_no_team_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.shopify.resource_service import configured_service

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-placeholder")
    monkeypatch.delenv("SUPABASE_TEAM_ID", raising=False)
    monkeypatch.delenv("BRAND_CONTEXT_TEAM_ID", raising=False)

    with pytest.raises(MissingSettingsError):
        configured_service()
