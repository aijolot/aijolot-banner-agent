from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class BrandAssetRepository:
    """Repository for public.brand_assets records."""

    table_name = "brand_assets"

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list_for_context(self, brand_context_id: str) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select("*")
            .eq("brand_context_id", brand_context_id)
            .order("created_at", desc=True)
        )
        return list(data or [])

    def create(self, brand_context_id: str, asset: dict[str, Any]) -> dict[str, Any]:
        payload = {**asset, "brand_context_id": brand_context_id}
        data = execute_data(self.client.table(self.table_name).insert(payload))
        if isinstance(data, list):
            return dict(data[0]) if data else {}
        return dict(data or {})

    def delete(self, asset_id: str) -> None:
        execute_data(self.client.table(self.table_name).delete().eq("id", asset_id))
