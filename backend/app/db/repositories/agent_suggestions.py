from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class AgentSuggestionRepository:
    table_name = "agent_suggestions"
    columns = (
        "id,team_id,kind,status,title,rationale,payload,source_refs,"
        "campaign_id,proposal_id,dedupe_key,expires_at,acted_at,created_at,updated_at"
    )
    writable_columns = {
        "team_id", "kind", "status", "title", "rationale", "payload", "source_refs",
        "campaign_id", "proposal_id", "dedupe_key", "expires_at", "acted_at",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def _row(self, out: Any) -> dict[str, Any]:
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {k: v for k, v in data.items() if k in self.writable_columns and v is not None}
        return self._row(execute_data(self.client.table(self.table_name).insert(payload).select(self.columns)))

    def get(self, *, suggestion_id: str, team_id: str | None = None) -> dict[str, Any] | None:
        query = self.client.table(self.table_name).select(self.columns).eq("id", suggestion_id)
        if team_id:
            query = query.eq("team_id", team_id)
        out = execute_data(query.limit(1))
        rows = out if isinstance(out, list) else ([out] if out else [])
        return dict(rows[0]) if rows else None

    def get_by_dedupe_key(self, *, team_id: str, dedupe_key: str) -> dict[str, Any] | None:
        out = execute_data(
            self.client.table(self.table_name).select(self.columns)
            .eq("team_id", team_id).eq("dedupe_key", dedupe_key).limit(1)
        )
        rows = out if isinstance(out, list) else ([out] if out else [])
        return dict(rows[0]) if rows else None

    def list(self, *, team_id: str, status: str | None = None, kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = self.client.table(self.table_name).select(self.columns).eq("team_id", team_id)
        if status:
            query = query.eq("status", status)
        if kind:
            query = query.eq("kind", kind)
        out = execute_data(query.order("created_at", desc=True).limit(limit))
        return [dict(row) for row in (out or [])] if isinstance(out, list) else ([dict(out)] if out else [])

    def update(self, *, suggestion_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {k: v for k, v in data.items() if k in self.writable_columns}
        out = execute_data(
            self.client.table(self.table_name).update(payload).eq("id", suggestion_id).select(self.columns)
        )
        rows = out if isinstance(out, list) else ([out] if out else [])
        return dict(rows[0]) if rows else None
