from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class PlacementTypeRepository:
    """Supabase repository for public.placement_types."""

    table_name = "placement_types"
    columns = "id,key,label,description,supported_targets,supported_slots,default_dimensions,config_schema,is_active,created_at"

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list_active(self) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("is_active", True)
            .order("key")
        )
        return list(data or [])

    def get_by_key(self, *, key: str) -> dict[str, Any] | None:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("key", key)
            .eq("is_active", True)
            .limit(1)
        )
        if isinstance(data, list):
            return dict(data[0]) if data else None
        return dict(data) if data else None

    def get_by_id(self, *, placement_type_id: str) -> dict[str, Any] | None:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("id", placement_type_id)
            .limit(1)
        )
        if isinstance(data, list):
            return dict(data[0]) if data else None
        return dict(data) if data else None
