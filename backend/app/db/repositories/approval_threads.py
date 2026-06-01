from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class ApprovalThreadRepository:
    table_name = "approval_threads"
    columns = "id,campaign_id,revision_id,status,approval_policy,requested_by,created_at,resolved_at"
    writable_columns = {"campaign_id", "revision_id", "status", "approval_policy", "requested_by", "resolved_at"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def get(self, *, thread_id: str) -> dict[str, Any] | None:
        out = execute_data(self.client.table(self.table_name).select(self.columns).eq("id", thread_id).limit(1))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def update(self, *, thread_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        if not payload:
            return self.get(thread_id=thread_id)
        out = execute_data(self.client.table(self.table_name).update(payload).eq("id", thread_id).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None
