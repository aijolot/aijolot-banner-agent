from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class RefinementRequestRepository:
    table_name = "refinement_requests"
    columns = (
        "id,campaign_id,source_revision_id,result_revision_id,requested_by,prompt,addressed_comment_ids,"
        "status,result_summary,created_at,finished_at"
    )
    writable_columns = {
        "campaign_id",
        "source_revision_id",
        "result_revision_id",
        "requested_by",
        "prompt",
        "addressed_comment_ids",
        "status",
        "result_summary",
        "finished_at",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def get(self, *, refinement_request_id: str) -> dict[str, Any] | None:
        out = execute_data(self.client.table(self.table_name).select(self.columns).eq("id", refinement_request_id).limit(1))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def list_by_campaign_id(self, *, campaign_id: str) -> list[dict[str, Any]]:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .order("created_at", desc=False)
        )
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def update(self, *, refinement_request_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        if not payload:
            return self.get(refinement_request_id=refinement_request_id)
        out = execute_data(
            self.client.table(self.table_name)
            .update(payload)
            .eq("id", refinement_request_id)
            .select(self.columns)
        )
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None
