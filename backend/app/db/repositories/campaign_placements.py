from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class CampaignPlacementRepository:
    """Supabase repository for public.campaign_placements."""

    table_name = "campaign_placements"
    columns = (
        "id,campaign_id,placement_type_id,mode,target_type,target_resource_gid,target_handle,target_title,"
        "existing_placement_key,existing_placement_label,existing_placement_size,slot,slot_order,scope_rule,layout_json,"
        "created_at,updated_at"
    )
    writable_columns = {
        "campaign_id",
        "placement_type_id",
        "mode",
        "target_type",
        "target_resource_gid",
        "target_handle",
        "target_title",
        "existing_placement_key",
        "existing_placement_label",
        "existing_placement_size",
        "slot",
        "slot_order",
        "scope_rule",
        "layout_json",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def get_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .limit(1)
        )
        if isinstance(data, list):
            return dict(data[0]) if data else None
        return dict(data) if data else None

    def upsert_for_campaign(self, *, campaign_id: str, data: dict[str, Any]) -> dict[str, Any]:
        payload = {"campaign_id": campaign_id, **data}
        payload = {key: value for key, value in payload.items() if key in self.writable_columns}
        out = execute_data(
            self.client.table(self.table_name)
            .upsert(payload, on_conflict="campaign_id")
            .select(self.columns)
        )
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})
