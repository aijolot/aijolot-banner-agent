from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class AgentJobRepository:
    table_name = "agent_jobs"
    columns = "id,team_id,kind,status,run_after,processing_started_at,attempt_count,error_detail,result_summary,created_at"
    writable_columns = {"team_id", "kind", "status", "run_after", "processing_started_at", "error_detail", "result_summary"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {k: v for k, v in data.items() if k in self.writable_columns and v is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def list_processing(self, *, limit: int = 50) -> list[dict[str, Any]]:
        out = execute_data(
            self.client.table(self.table_name).select(self.columns)
            .eq("status", "processing").order("processing_started_at").limit(limit)
        )
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def mark_done(self, job_id: str, *, result_summary: dict[str, Any] | None = None) -> dict[str, Any] | None:
        out = execute_data(
            self.client.table(self.table_name)
            .update({"status": "done", "result_summary": result_summary or {}})
            .eq("id", job_id).select(self.columns)
        )
        rows = out if isinstance(out, list) else ([out] if out else [])
        return dict(rows[0]) if rows else None

    def mark_error(self, job_id: str, *, error_detail: str) -> dict[str, Any] | None:
        out = execute_data(
            self.client.table(self.table_name)
            .update({"status": "error", "error_detail": error_detail[:500]})
            .eq("id", job_id).select(self.columns)
        )
        rows = out if isinstance(out, list) else ([out] if out else [])
        return dict(rows[0]) if rows else None
