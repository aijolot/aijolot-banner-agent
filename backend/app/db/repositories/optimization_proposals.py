from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class OptimizationProposalRepository:
    table_name = "optimization_proposals"
    columns = "id,campaign_id,source_revision_id,proposed_revision_id,segment_key,rationale,projected_lift,status,created_at,updated_at"
    writable_columns = {"campaign_id", "source_revision_id", "proposed_revision_id", "segment_key", "rationale", "projected_lift", "status"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list_by_campaign_id(self, *, campaign_id: str, limit: int = 20) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .order("updated_at", desc=True)
            .limit(limit)
        )
        return [dict(row) for row in (data or [])]

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})
