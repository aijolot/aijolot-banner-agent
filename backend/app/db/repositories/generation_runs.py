from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class GenerationRunRepository:
    """Supabase repository for public.generation_runs."""

    table_name = "generation_runs"
    columns = (
        "id,campaign_id,parent_run_id,run_type,status,frontend_step,adk_trace_id,"
        "started_by,started_at,finished_at,error_message,metadata,created_at"
    )
    writable_columns = {
        "campaign_id",
        "parent_run_id",
        "run_type",
        "status",
        "frontend_step",
        "adk_trace_id",
        "started_by",
        "started_at",
        "finished_at",
        "error_message",
        "metadata",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def get(self, *, run_id: str) -> dict[str, Any] | None:
        data = execute_data(self.client.table(self.table_name).select(self.columns).eq("id", run_id).limit(1))
        if isinstance(data, list):
            return dict(data[0]) if data else None
        return dict(data) if data else None

    def update(self, *, run_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns}
        if not payload:
            return self.get(run_id=run_id)
        out = execute_data(self.client.table(self.table_name).update(payload).eq("id", run_id).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .order("created_at", desc=True)
            .order("id", desc=True)
            .limit(1)
        )
        if isinstance(data, list):
            return dict(data[0]) if data else None
        return dict(data) if data else None
