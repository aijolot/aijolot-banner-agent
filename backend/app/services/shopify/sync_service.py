"""Live Shopify catalog sync into the resource cache (F3).

Reads products/collections/vendors/customer-segments via the Admin GraphQL API
and upserts them into shopify_resource_cache. The storefront/UI never depends on
live latency — they read the cache; only an explicit sync touches the API.
"""

from __future__ import annotations

from typing import Any

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.shopify_resource_cache import ShopifyResourceCacheRepository
from app.db.repositories.stores import StoreRepository
from app.services.shopify import graphql_queries as gq
from app.services.shopify.admin_factory import configured_admin_client
from app.services.shopify.client import ShopifyAdminClient, ShopifyApiError
from app.services.shopify.resource_service import StoreNotFound
from app.services.supabase.client import SupabaseClientFactory

DEFAULT_RESOURCE_TYPES = ["product", "collection", "vendor", "customer_segment"]
_PAGE_SIZE = 50
_MAX_PAGES = 20  # safety bound: up to 1000 items per type


class ShopifyCatalogSyncService:
    def __init__(
        self,
        *,
        client: ShopifyAdminClient,
        cache_repository: ShopifyResourceCacheRepository,
        store_repository: StoreRepository,
        team_id: str | None = None,
    ) -> None:
        self.client = client
        self.cache_repository = cache_repository
        self.store_repository = store_repository
        self.team_id = team_id

    @classmethod
    def from_env(cls, *, team_id: str | None = None) -> "ShopifyCatalogSyncService":
        settings = Settings.from_env()
        client = configured_admin_client(settings)  # raises MissingSettingsError without creds
        if settings.supabase_url is None or settings.supabase_service_role_key is None:
            raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
        supabase = SupabaseClientFactory(settings).service_role_client()
        return cls(
            client=client,
            cache_repository=ShopifyResourceCacheRepository(supabase),
            store_repository=StoreRepository(supabase),
            team_id=team_id or settings.supabase_team_id,
        )

    def sync_store(self, store_id: str, *, resource_types: list[str] | None = None, dry_run: bool = False) -> dict[str, Any]:
        store = self.store_repository.get(store_id=store_id, team_id=self.team_id)
        if store is None:
            raise StoreNotFound(store_id)
        types = resource_types or DEFAULT_RESOURCE_TYPES
        results: list[dict[str, Any]] = []
        warnings: list[str] = []

        # products + derived vendors share one product fetch.
        product_rows: list[dict[str, Any]] = []
        if "product" in types or "vendor" in types:
            try:
                product_rows = self._fetch_products()
            except ShopifyApiError as exc:
                warnings.append(f"products fetch failed: {exc}")

        if "product" in types:
            results.append(self._write("product", product_rows, store_id, dry_run))
        if "vendor" in types:
            vendor_rows = self._derive_vendors(product_rows)
            results.append(self._write("vendor", vendor_rows, store_id, dry_run))
        if "collection" in types:
            try:
                rows = self._fetch_collections()
                results.append(self._write("collection", rows, store_id, dry_run))
            except ShopifyApiError as exc:
                warnings.append(f"collections fetch failed: {exc}")
        if "customer_segment" in types:
            try:
                rows = self._fetch_segments()
                results.append(self._write("customer_segment", rows, store_id, dry_run))
            except ShopifyApiError as exc:
                warnings.append(
                    "customer segments unavailable (check read_customers/segments scope): " + str(exc)
                )

        return {
            "store_id": store_id,
            "source": "shopify_admin_graphql",
            "dry_run": dry_run,
            "results": results,
            "warnings": warnings,
        }

    # --- fetch helpers (paginated) ---
    def _paginate(self, query: str, root_key: str) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        after: str | None = None
        for _ in range(_MAX_PAGES):
            data = self.client.graphql(query, {"first": _PAGE_SIZE, "after": after})
            conn = data.get(root_key) or {}
            for edge in conn.get("edges", []):
                node = edge.get("node")
                if node:
                    nodes.append(node)
            page = conn.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            after = page.get("endCursor")
        return nodes

    def _fetch_products(self) -> list[dict[str, Any]]:
        return [gq.product_to_row(n) for n in self._paginate(gq.PRODUCTS_QUERY, "products")]

    def _fetch_collections(self) -> list[dict[str, Any]]:
        return [gq.collection_to_row(n) for n in self._paginate(gq.COLLECTIONS_QUERY, "collections")]

    def _fetch_segments(self) -> list[dict[str, Any]]:
        return [gq.segment_to_row(n) for n in self._paginate(gq.SEGMENTS_QUERY, "segments")]

    @staticmethod
    def _derive_vendors(product_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for row in product_rows:
            vendor = (row.get("vendor") or "").strip()
            if vendor and vendor not in seen:
                seen[vendor] = gq.vendor_to_row(vendor)
        return list(seen.values())

    def _write(self, resource_type: str, rows: list[dict[str, Any]], store_id: str, dry_run: bool) -> dict[str, Any]:
        written = 0
        if not dry_run:
            written = self.cache_repository.upsert_many(store_id=store_id, resource_type=resource_type, rows=rows)
        return {"resource_type": resource_type, "fetched": len(rows), "written": written, "skipped": 0}
