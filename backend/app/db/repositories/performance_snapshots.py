from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class PerformanceSnapshotRepository:
    table_name = "performance_snapshots"
    columns = "id,campaign_id,revision_id,source,window_start,window_end,impressions,clicks,ctr,conversions,conversion_rate,load_p75_ms,weight_saved_pct,segment_breakdown,trend,created_at"
    writable_columns = {"campaign_id", "revision_id", "source", "window_start", "window_end", "impressions", "clicks", "ctr", "conversions", "conversion_rate", "load_p75_ms", "weight_saved_pct", "segment_breakdown", "trend"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list_by_campaign_id(self, *, campaign_id: str, limit: int = 20) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        return [dict(row) for row in (data or [])]

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})
