from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class CampaignRepository:
    """Supabase repository for public.campaigns."""

    table_name = "campaigns"
    writable_columns = {
        "team_id",
        "store_id",
        "brand_context_id",
        "title",
        "promo_label",
        "promo_rule",
        "raw_brief",
        "structured_brief",
        "status",
        "created_by",
        "selected_revision_id",
        "archived_at",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list(self, *, team_id: str, limit: int = 100) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select("*")
            .eq("team_id", team_id)
            .is_("archived_at", "null")
            .order("updated_at", desc=True)
            .limit(limit)
        )
        return list(data or [])

    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None:
        query = self.client.table(self.table_name).select("*").eq("id", campaign_id).is_("archived_at", "null").limit(1)
        if team_id:
            query = query.eq("team_id", team_id)
        data = execute_data(query)
        if isinstance(data, list):
            return dict(data[0]) if data else None
        return dict(data) if data else None

    def create(
        self,
        *,
        team_id: str,
        store_id: str,
        title: str,
        raw_brief: str = "",
        structured_brief: dict[str, Any] | None = None,
        status: str = "draft",
        created_by: str | None = None,
        brand_context_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "team_id": team_id,
            "store_id": store_id,
            "title": title or "Nueva campaña",
            "raw_brief": raw_brief,
            "structured_brief": structured_brief or {},
            "status": status,
            "created_by": created_by,
            "brand_context_id": brand_context_id,
        }
        payload = {key: value for key, value in payload.items() if key in self.writable_columns and value is not None}
        data = execute_data(self.client.table(self.table_name).insert(payload))
        if isinstance(data, list):
            return dict(data[0]) if data else {}
        return dict(data or {})

    def update(self, *, campaign_id: str, data: dict[str, Any], team_id: str | None = None) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        if not payload:
            return self.get(campaign_id=campaign_id, team_id=team_id)
        query = self.client.table(self.table_name).update(payload).eq("id", campaign_id)
        if team_id:
            query = query.eq("team_id", team_id)
        out = execute_data(query)
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def first_store_id(self, *, team_id: str) -> str | None:
        data = execute_data(self.client.table("stores").select("id").eq("team_id", team_id).limit(1))
        if isinstance(data, list):
            return str(data[0]["id"]) if data else None
        return str(data["id"]) if data and "id" in data else None
