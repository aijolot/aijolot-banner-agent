from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class CampaignRevisionRepository:
    """Thin Supabase adapter for public.campaign_revisions."""

    table_name = "campaign_revisions"
    columns = (
        "id,campaign_id,generation_run_id,revision_number,status,concept,liquid_config,"
        "html_preview,preview_storage_path,created_at"
    )
    writable_columns = {
        "campaign_id",
        "generation_run_id",
        "revision_number",
        "status",
        "concept",
        "liquid_config",
        "html_preview",
        "preview_storage_path",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def get(self, *, revision_id: str) -> dict[str, Any] | None:
        out = execute_data(self.client.table(self.table_name).select(self.columns).eq("id", revision_id).limit(1))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .order("revision_number", desc=True)
            .limit(1)
        )
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def list_by_campaign_id(self, *, campaign_id: str) -> list[dict[str, Any]]:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .order("revision_number", desc=False)
        )
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def update(self, *, revision_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        if not payload:
            return self.get(revision_id=revision_id)
        out = execute_data(self.client.table(self.table_name).update(payload).eq("id", revision_id).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None
