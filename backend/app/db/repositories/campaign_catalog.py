from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class CampaignCatalogRepository:
    """Supabase repository for campaign catalog snapshot tables."""

    snapshot_table = "campaign_catalog_snapshots"
    item_table = "campaign_catalog_items"
    snapshot_columns = "id,campaign_id,source,query_summary,discount_rule,created_at"
    item_columns = "id,snapshot_id,shopify_product_gid,shopify_variant_gid,sku,title,segment_key,price,sale_price,stock,image_url,raw"

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create_snapshot(
        self,
        *,
        campaign_id: str,
        source: str,
        query_summary: str | None,
        discount_rule: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        snapshot_payload = {
            "campaign_id": campaign_id,
            "source": source,
            "query_summary": query_summary,
            "discount_rule": discount_rule or {},
        }
        snapshot_data = execute_data(
            self.client.table(self.snapshot_table)
            .insert(snapshot_payload)
            .select(self.snapshot_columns)
        )
        if isinstance(snapshot_data, list):
            snapshot = dict(snapshot_data[0]) if snapshot_data else {}
        else:
            snapshot = dict(snapshot_data or {})
        snapshot_id = str(snapshot.get("id") or "")
        inserted_items: list[dict[str, Any]] = []
        if snapshot_id and items:
            payload = [self._item_payload(snapshot_id=snapshot_id, item=item) for item in items]
            try:
                item_data = execute_data(
                    self.client.table(self.item_table)
                    .insert(payload)
                    .select(self.item_columns)
                )
            except Exception:
                self.delete_snapshot(snapshot_id=snapshot_id)
                raise
            inserted_items = [dict(row) for row in item_data] if isinstance(item_data, list) else ([dict(item_data)] if item_data else [])
        snapshot["items"] = inserted_items
        return snapshot

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        snapshot_data = execute_data(
            self.client.table(self.snapshot_table)
            .select(self.snapshot_columns)
            .eq("campaign_id", campaign_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        if isinstance(snapshot_data, list):
            snapshot = dict(snapshot_data[0]) if snapshot_data else None
        else:
            snapshot = dict(snapshot_data) if snapshot_data else None
        if not snapshot:
            return None
        item_data = execute_data(
            self.client.table(self.item_table)
            .select(self.item_columns)
            .eq("snapshot_id", snapshot["id"])
            .order("title")
        )
        snapshot["items"] = [dict(row) for row in item_data] if isinstance(item_data, list) else ([dict(item_data)] if item_data else [])
        return snapshot

    def delete_snapshot(self, *, snapshot_id: str) -> None:
        execute_data(self.client.table(self.item_table).delete().eq("snapshot_id", snapshot_id))
        execute_data(self.client.table(self.snapshot_table).delete().eq("id", snapshot_id))

    @staticmethod
    def _item_payload(*, snapshot_id: str, item: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "shopify_product_gid",
            "shopify_variant_gid",
            "sku",
            "title",
            "segment_key",
            "price",
            "sale_price",
            "stock",
            "image_url",
            "raw",
        }
        payload = {key: value for key, value in item.items() if key in allowed}
        payload["snapshot_id"] = snapshot_id
        payload.setdefault("raw", {})
        return payload
