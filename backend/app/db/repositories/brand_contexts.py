from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class BrandContextRepository:
    """Supabase repository for public.brand_contexts.

    Runtime lookup is by (team_id, slug). The database UUID remains internal;
    API compatibility exposes the slug as BrandContext.id.
    """

    table_name = "brand_contexts"
    writable_columns = {
        "team_id",
        "store_id",
        "name",
        "slug",
        "description",
        "palette",
        "typography",
        "voice",
        "allowed_rules",
        "forbidden_rules",
        "required_phrases",
        "prohibited_words",
        "image_style_directives",
        "logo_url",
        "source_file_path",
        "source_metadata",
        "created_by",
        "archived_at",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list(self, *, team_id: str) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select("*")
            .eq("team_id", team_id)
            .is_("archived_at", "null")
            .order("name")
        )
        return list(data or [])

    def get_by_slug(self, *, team_id: str, slug: str) -> dict[str, Any] | None:
        data = execute_data(
            self.client.table(self.table_name)
            .select("*")
            .eq("team_id", team_id)
            .eq("slug", slug)
            .is_("archived_at", "null")
            .limit(1)
        )
        if isinstance(data, list):
            return dict(data[0]) if data else None
        return dict(data) if data else None

    def upsert(
        self,
        *,
        team_id: str,
        slug: str,
        data: dict[str, Any],
        store_id: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        shaped_data = {key: value for key, value in data.items() if key in self.writable_columns}
        payload = {
            **shaped_data,
            "team_id": team_id,
            "slug": slug,
            "store_id": store_id,
            "created_by": created_by,
            "archived_at": None,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        query = self.client.table(self.table_name).upsert(payload, on_conflict="team_id,slug")
        data_out = execute_data(query)
        if isinstance(data_out, list):
            return dict(data_out[0]) if data_out else {}
        return dict(data_out or {})

    def archive(self, *, team_id: str, slug: str) -> None:
        execute_data(
            self.client.table(self.table_name)
            .update({"archived_at": datetime.now(UTC).isoformat()})
            .eq("team_id", team_id)
            .eq("slug", slug)
            .is_("archived_at", "null")
        )
