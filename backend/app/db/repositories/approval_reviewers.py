from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class ApprovalReviewerRepository:
    table_name = "approval_reviewers"
    columns = "id,approval_thread_id,user_id,role_label,status,note,decided_at,created_at,updated_at"
    writable_columns = {"approval_thread_id", "user_id", "role_label", "status", "note", "decided_at"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create_many(self, *, reviewers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payload = [
            {key: value for key, value in reviewer.items() if key in self.writable_columns and value is not None}
            for reviewer in reviewers
        ]
        if not payload:
            return []
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        return [dict(row) for row in (out or [])] if isinstance(out, list) else [dict(out)]

    def list_by_thread_id(self, *, thread_id: str) -> list[dict[str, Any]]:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("approval_thread_id", thread_id)
            .order("created_at", desc=False)
        )
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def get_for_user(self, *, thread_id: str, user_id: str) -> dict[str, Any] | None:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("approval_thread_id", thread_id)
            .eq("user_id", user_id)
            .limit(1)
        )
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def update_for_user(self, *, thread_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        if not payload:
            return self.get_for_user(thread_id=thread_id, user_id=user_id)
        out = execute_data(
            self.client.table(self.table_name)
            .update(payload)
            .eq("approval_thread_id", thread_id)
            .eq("user_id", user_id)
            .select(self.columns)
        )
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None
