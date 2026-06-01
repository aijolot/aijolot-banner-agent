from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class AuditEventRepository:
    """Thin Supabase adapter for public.audit_events."""

    table_name = "audit_events"
    columns = (
        "id,team_id,campaign_id,trace_id,session_id,actor_type,actor_id,node,event_type,"
        "duration_ms,cost_usd,audit_pass,review_decision,shopify_section_id,payload,created_at"
    )
    writable_columns = {
        "team_id",
        "campaign_id",
        "trace_id",
        "session_id",
        "actor_type",
        "actor_id",
        "node",
        "event_type",
        "duration_ms",
        "cost_usd",
        "audit_pass",
        "review_decision",
        "shopify_section_id",
        "payload",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        payload.setdefault("actor_type", "agent")
        payload.setdefault("payload", {})
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def list_by_campaign_id(self, *, campaign_id: str, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 200))
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .order("created_at", desc=True)
            .limit(safe_limit)
        )
        return [dict(row) for row in (out or [])]
