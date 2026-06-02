from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class GenerationUsageEventRepository:
    """Supabase adapter for public.generation_usage_events.

    The service can run without this repository; this adapter is intentionally
    thin so tests can use in-memory tracking and production can persist events
    once Supabase auth wiring is available.
    """

    table_name = "generation_usage_events"
    columns = "id,user_id,team_id,campaign_id,event_type,provider,model,estimated_cost_usd,metadata,created_at"
    writable_columns = {
        "user_id",
        "team_id",
        "campaign_id",
        "event_type",
        "provider",
        "model",
        "estimated_cost_usd",
        "metadata",
        "created_at",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: _json_safe(value) for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def count_since(self, *, user_id: str, event_type: str, since: datetime) -> int:
        data = execute_data(
            self.client.table(self.table_name)
            .select("id")
            .eq("user_id", user_id)
            .eq("event_type", event_type)
            .gte("created_at", since.isoformat())
        )
        return len(list(data or []))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value
