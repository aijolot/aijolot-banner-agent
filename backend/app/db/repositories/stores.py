from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class StoreRepository:
    """Supabase repository for public.stores."""

    table_name = "stores"
    safe_columns = (
        "id,team_id,shop_domain,display_name,shopify_api_version,theme_id,"
        "banner_metafield_namespace,banner_metafield_key,status,created_at,updated_at"
    )

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list(self, *, team_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = self.client.table(self.table_name).select(self.safe_columns).order("display_name").limit(limit)
        if team_id:
            query = query.eq("team_id", team_id)
        data = execute_data(query)
        return list(data or [])

    def get(self, *, store_id: str, team_id: str | None = None) -> dict[str, Any] | None:
        query = self.client.table(self.table_name).select(self.safe_columns).eq("id", store_id).limit(1)
        if team_id:
            query = query.eq("team_id", team_id)
        data = execute_data(query)
        if isinstance(data, list):
            return dict(data[0]) if data else None
        return dict(data) if data else None
