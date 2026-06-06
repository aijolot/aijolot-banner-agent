from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class BannerVariantRepository:
    """Thin Supabase adapter for public.banner_variants."""

    table_name = "banner_variants"
    columns = (
        "id,revision_id,segment_key,segment_label,customer_tag,audience_rule,product_snapshot_item_id,"
        "eyebrow,headline,subheadline,cta_text,cta_url,palette"
    )
    writable_columns = {
        "revision_id",
        "segment_key",
        "segment_label",
        "customer_tag",
        "audience_rule",
        "product_snapshot_item_id",
        "eyebrow",
        "headline",
        "subheadline",
        "cta_text",
        "cta_url",
        "palette",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def create_many(self, *, variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not variants:
            return []
        payload = [
            {key: value for key, value in row.items() if key in self.writable_columns and value is not None}
            for row in variants
        ]
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def update(self, *, variant_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns}
        if not payload:
            return None
        out = execute_data(self.client.table(self.table_name).update(payload).eq("id", variant_id).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def get(self, *, variant_id: str) -> dict[str, Any] | None:
        out = execute_data(self.client.table(self.table_name).select(self.columns).eq("id", variant_id).limit(1))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def list_by_revision_id(self, *, revision_id: str) -> list[dict[str, Any]]:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("revision_id", revision_id)
            .order("segment_key", desc=False)
        )
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])
