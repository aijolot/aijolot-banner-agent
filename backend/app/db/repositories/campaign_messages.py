from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class CampaignMessageRepository:
    """Supabase repository for public.campaign_messages."""

    table_name = "campaign_messages"
    writable_columns = {"campaign_id", "author_type", "author_id", "body", "metadata"}

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list_for_campaign(self, *, campaign_id: str) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select("*")
            .eq("campaign_id", campaign_id)
            .order("created_at")
        )
        return list(data or [])

    def create(
        self,
        *,
        campaign_id: str,
        author_type: str,
        body: str,
        metadata: dict[str, Any] | None = None,
        author_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "campaign_id": campaign_id,
            "author_type": author_type,
            "author_id": author_id,
            "body": body,
            "metadata": metadata or {},
        }
        payload = {key: value for key, value in payload.items() if key in self.writable_columns and value is not None}
        data = execute_data(self.client.table(self.table_name).insert(payload))
        if isinstance(data, list):
            return dict(data[0]) if data else {}
        return dict(data or {})
