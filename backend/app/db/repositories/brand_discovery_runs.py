from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class BrandDiscoveryRunRepository:
    """Supabase repository for public.brand_discovery_runs.

    One row per discovery run (history/debuggability). ``brand_id`` is the
    runtime brand slug (BrandContext.id), mirroring how the API addresses
    brands; the latest applied evidence also lives on
    ``brand_contexts.discovery_snapshot``.
    """

    table_name = "brand_discovery_runs"
    writable_columns = {
        "team_id",
        "store_id",
        "brand_id",
        "status",
        "snapshot",
        "recommendation",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def insert(
        self,
        *,
        team_id: str,
        brand_id: str,
        status: str = "pending",
        snapshot: dict[str, Any] | None = None,
        recommendation: dict[str, Any] | None = None,
        store_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "team_id": team_id,
            "brand_id": brand_id,
            "store_id": store_id,
            "status": status,
            "snapshot": snapshot,
            "recommendation": recommendation,
        }
        payload = {key: value for key, value in payload.items() if key in self.writable_columns and value is not None}
        data = execute_data(self.client.table(self.table_name).insert(payload))
        if isinstance(data, list):
            return dict(data[0]) if data else {}
        return dict(data or {})

    def get(self, *, run_id: str, team_id: str | None = None) -> dict[str, Any] | None:
        query = self.client.table(self.table_name).select("*").eq("id", run_id).limit(1)
        if team_id:
            query = query.eq("team_id", team_id)
        data = execute_data(query)
        if isinstance(data, list):
            return dict(data[0]) if data else None
        return dict(data) if data else None

    def list_for_brand(self, *, team_id: str, brand_id: str, limit: int = 20) -> list[dict[str, Any]]:
        data = execute_data(
            self.client.table(self.table_name)
            .select("*")
            .eq("team_id", team_id)
            .eq("brand_id", brand_id)
            .order("created_at", desc=True)
            .order("id", desc=True)
            .limit(limit)
        )
        return list(data or [])

    def update_status(
        self,
        *,
        run_id: str,
        status: str,
        team_id: str | None = None,
        snapshot: dict[str, Any] | None = None,
        recommendation: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"status": status}
        if snapshot is not None:
            payload["snapshot"] = snapshot
        if recommendation is not None:
            payload["recommendation"] = recommendation
        query = self.client.table(self.table_name).update(payload).eq("id", run_id)
        if team_id:
            query = query.eq("team_id", team_id)
        out = execute_data(query)
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None
