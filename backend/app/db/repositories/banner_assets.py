from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class BannerAssetRepository:
    """Thin Supabase adapter for public.banner_assets."""

    table_name = "banner_assets"
    columns = (
        "id,banner_variant_id,revision_id,asset_kind,size_key,width,height,format,"
        "storage_path,public_url,alt_text,bytes,image_prompt,metadata,created_at"
    )
    writable_columns = {
        "banner_variant_id",
        "revision_id",
        "asset_kind",
        "size_key",
        "width",
        "height",
        "format",
        "storage_path",
        "public_url",
        "alt_text",
        "bytes",
        "image_prompt",
        "metadata",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def create_many(self, *, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not assets:
            return []
        payload = [
            {key: value for key, value in asset.items() if key in self.writable_columns and value is not None}
            for asset in assets
        ]
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return [dict(row) for row in out]
        return [dict(out)] if out else []

    def list_by_revision_id(self, *, revision_id: str, asset_kind: str | None = None) -> list[dict[str, Any]]:
        query = self.client.table(self.table_name).select(self.columns).eq("revision_id", revision_id)
        if asset_kind:
            query = query.eq("asset_kind", asset_kind)
        out = execute_data(query.order("size_key").order("format"))
        return [dict(row) for row in (out or [])]

    def list_by_banner_variant_id(self, *, banner_variant_id: str, asset_kind: str | None = None) -> list[dict[str, Any]]:
        query = self.client.table(self.table_name).select(self.columns).eq("banner_variant_id", banner_variant_id)
        if asset_kind:
            query = query.eq("asset_kind", asset_kind)
        out = execute_data(query.order("size_key").order("format"))
        return [dict(row) for row in (out or [])]
