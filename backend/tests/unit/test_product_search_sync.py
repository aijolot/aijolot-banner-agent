"""On-demand product search+sync (resolve live, persist to cache)."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.shopify.client import ShopifyApiError
from app.services.shopify.resource_service import StoreNotFound
from app.services.shopify.sync_service import ShopifyCatalogSyncService


class _FakeClient:
    def __init__(self, data: dict[str, Any] | Exception) -> None:
        self._data = data
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((query, variables))
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class _FakeCache:
    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []

    def upsert_many(self, *, store_id: str, resource_type: str, rows: list[dict[str, Any]]) -> int:
        self.upserts.append({"store_id": store_id, "resource_type": resource_type, "rows": rows})
        return len(rows)


class _FakeStores:
    def __init__(self, exists: bool = True) -> None:
        self._exists = exists

    def get(self, *, store_id: str, team_id: str | None = None) -> dict[str, Any] | None:
        return {"id": store_id} if self._exists else None


def _products_payload() -> dict[str, Any]:
    return {
        "products": {
            "edges": [
                {
                    "node": {
                        "id": "gid://shopify/Product/14988752617842",
                        "handle": "odyssey-mandarin-sky",
                        "title": "Odyssey Mandarin Sky EDP 100ml Hombre",
                        "vendor": "Armaf",
                        "status": "ACTIVE",
                        "tags": ["citrus", "men"],
                        "totalInventory": 42,
                        "featuredImage": {"url": "https://cdn.shopify.com/mandarin.jpg"},
                        "priceRangeV2": {"minVariantPrice": {"amount": "59.90", "currencyCode": "USD"}},
                    }
                }
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }
    }


def _service(client: _FakeClient, cache: _FakeCache, stores: _FakeStores) -> ShopifyCatalogSyncService:
    return ShopifyCatalogSyncService(
        client=client, cache_repository=cache, store_repository=stores, team_id="team-1"
    )


def test_search_resolves_live_and_persists_with_image_and_inventory() -> None:
    client = _FakeClient(_products_payload())
    cache = _FakeCache()
    svc = _service(client, cache, _FakeStores())

    report = svc.search_and_sync_products("store-1", query="Mandarin Sky", limit=10)

    # Live query carried the search term + bounded page size.
    assert client.calls[0][1]["query"] == "Mandarin Sky"
    assert client.calls[0][1]["first"] == 10
    assert report["matched"] == 1
    assert report["written"] == 1
    item = report["items"][0]
    assert item["shopify_gid"] == "gid://shopify/Product/14988752617842"
    assert item["image_url"] == "https://cdn.shopify.com/mandarin.jpg"
    # Real stats fetched (inventory/price), nothing fabricated.
    assert item["raw"]["total_inventory"] == 42
    assert item["raw"]["price"] == "59.90"
    # Persisted into the product cache the snapshot reads from.
    assert cache.upserts[0]["resource_type"] == "product"


def test_dry_run_resolves_but_does_not_write() -> None:
    client = _FakeClient(_products_payload())
    cache = _FakeCache()
    svc = _service(client, cache, _FakeStores())

    report = svc.search_and_sync_products("store-1", query="Mandarin", dry_run=True)

    assert report["matched"] == 1
    assert report["written"] == 0
    assert cache.upserts == []


def test_blank_query_short_circuits() -> None:
    client = _FakeClient(_products_payload())
    cache = _FakeCache()
    svc = _service(client, cache, _FakeStores())

    report = svc.search_and_sync_products("store-1", query="   ")

    assert report["matched"] == 0
    assert client.calls == []


def test_unknown_store_raises() -> None:
    svc = _service(_FakeClient(_products_payload()), _FakeCache(), _FakeStores(exists=False))
    with pytest.raises(StoreNotFound):
        svc.search_and_sync_products("missing", query="Mandarin")


def test_shopify_error_degrades_gracefully() -> None:
    client = _FakeClient(ShopifyApiError("rate limited"))
    cache = _FakeCache()
    svc = _service(client, cache, _FakeStores())

    report = svc.search_and_sync_products("store-1", query="Mandarin")

    assert report["matched"] == 0
    assert report["written"] == 0
    assert report["warnings"]
