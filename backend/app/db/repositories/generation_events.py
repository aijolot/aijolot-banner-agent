from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class GenerationEventRepository:
    """Supabase repository for public.generation_events."""

    table_name = "generation_events"
    columns = (
        "id,generation_run_id,node_key,frontend_step,status,input_summary,"
        "output_summary,duration_ms,cost_usd,created_at"
    )
    writable_columns = {
        "generation_run_id",
        "node_key",
        "frontend_step",
        "status",
        "input_summary",
        "output_summary",
        "duration_ms",
        "cost_usd",
        "created_at",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create_many(self, *, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not events:
            return []
        payload = [
            {key: value for key, value in event.items() if key in self.writable_columns and value is not None}
            for event in events
        ]
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return [dict(row) for row in out]
        return [dict(out)] if out else []

    def list_by_run_id(self, *, run_id: str) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("generation_run_id", run_id)
            .order("created_at", desc=False)
            .order("id", desc=False)
        )
        return [dict(row) for row in list(data or [])]
