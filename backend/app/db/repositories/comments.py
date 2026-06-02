from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class CommentRepository:
    table_name = "comments"
    columns = (
        "id,approval_thread_id,campaign_id,revision_id,banner_variant_id,layout_variant_key,device_key,"
        "author_id,body,pin_x,pin_y,resolved,resolved_by,resolved_at,created_at,updated_at"
    )
    writable_columns = {
        "approval_thread_id",
        "campaign_id",
        "revision_id",
        "banner_variant_id",
        "layout_variant_key",
        "device_key",
        "author_id",
        "body",
        "pin_x",
        "pin_y",
        "resolved",
        "resolved_by",
        "resolved_at",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def get(self, *, comment_id: str) -> dict[str, Any] | None:
        out = execute_data(self.client.table(self.table_name).select(self.columns).eq("id", comment_id).limit(1))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def list_by_thread_id(self, *, thread_id: str) -> list[dict[str, Any]]:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("approval_thread_id", thread_id)
            .order("created_at", desc=False)
        )
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def update(self, *, comment_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        if not payload:
            return self.get(comment_id=comment_id)
        out = execute_data(self.client.table(self.table_name).update(payload).eq("id", comment_id).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None
