from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class OptimizationInsightRepository:
    table_name = "optimization_insights"
    columns = "id,team_id,campaign_id,segment_key,tag,insight,lift_label,source,created_at"

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list_for_team_and_campaign(self, *, team_id: str, campaign_id: str, limit: int = 20) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("team_id", team_id)
            .or_(f"campaign_id.is.null,campaign_id.eq.{campaign_id}")
            .order("created_at", desc=True)
            .limit(limit)
        )
        return [dict(row) for row in (data or [])]
