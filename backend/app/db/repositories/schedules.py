from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class ScheduleRepository:
    table_name = "schedules"
    columns = "id,campaign_id,revision_id,starts_at,ends_at,timezone,auto_unpublish,status,created_by,created_at,updated_at"
    writable_columns = {"campaign_id", "revision_id", "starts_at", "ends_at", "timezone", "auto_unpublish", "status", "created_by"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def get_active_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .in_("status", ("pending", "active"))
            .order("starts_at", desc=True)
            .limit(1)
        )
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def update(self, *, schedule_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        if not payload:
            return None
        out = execute_data(self.client.table(self.table_name).update(payload).eq("id", schedule_id).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None
