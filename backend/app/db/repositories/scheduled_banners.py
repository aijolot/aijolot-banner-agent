from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class ScheduledBannerRepository:
    table_name = "scheduled_banners"
    columns = "id,campaign_id,brand_id,payload,target_publish_at,status,created_at"
    writable_columns = {"campaign_id", "brand_id", "payload", "target_publish_at", "status"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def list_due(self, *, limit: int = 50) -> list[dict[str, Any]]:
        out = execute_data(self.client.table(self.table_name).select(self.columns).eq("status", "pending").order("target_publish_at").limit(limit))
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def list_processing(self, *, limit: int = 50) -> list[dict[str, Any]]:
        out = execute_data(self.client.table(self.table_name).select(self.columns).eq("status", "processing").order("processing_started_at").limit(limit))
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def mark_published(self, row_id: str) -> dict[str, Any] | None:
        payload = {"status": "published"}
        out = execute_data(
            self.client.table(self.table_name)
            .update(payload)
            .eq("id", row_id)
            .select(self.columns)
        )
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None
