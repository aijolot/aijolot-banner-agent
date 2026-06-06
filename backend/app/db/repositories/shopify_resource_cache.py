from __future__ import annotations

from typing import Any, Literal

from app.db.repositories._supabase import SupabaseClient, execute_data

CachedResourceType = Literal["collection", "product", "page", "vendor", "customer_segment"]

_WRITABLE_COLUMNS = ("store_id", "resource_type", "shopify_gid", "handle", "title", "vendor", "tags", "image_url", "status", "raw")


class ShopifyResourceCacheRepository:
    """Supabase repository for public.shopify_resource_cache (read + sync writes)."""

    table_name = "shopify_resource_cache"
    columns = "id,store_id,resource_type,shopify_gid,handle,title,vendor,tags,image_url,status,raw,synced_at"

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list_for_store(self, *, store_id: str, resource_type: CachedResourceType | str, limit: int = 100) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("store_id", store_id)
            .eq("resource_type", resource_type)
            .order("title")
            .limit(limit)
        )
        return list(data or [])

    def upsert_many(self, *, store_id: str, resource_type: str, rows: list[dict[str, Any]]) -> int:
        """Upsert cached resources for one (store, resource_type) by shopify_gid.

        Returns the number of rows written. Conflicts on the table's
        (store_id, resource_type, shopify_gid) unique key are merged.
        """

        if not rows:
            return 0
        payload = []
        for row in rows:
            record = {key: row.get(key) for key in _WRITABLE_COLUMNS if row.get(key) is not None}
            record["store_id"] = store_id
            record["resource_type"] = resource_type
            payload.append(record)
        execute_data(
            self.client.table(self.table_name)
            .upsert(payload, on_conflict="store_id,resource_type,shopify_gid")
            .select("id")
        )
        return len(payload)
