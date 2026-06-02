from __future__ import annotations

from typing import Any, Literal

from app.db.repositories._supabase import SupabaseClient, execute_data

CachedResourceType = Literal["collection", "product", "page"]


class ShopifyResourceCacheRepository:
    """Read-only Supabase repository for public.shopify_resource_cache."""

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
