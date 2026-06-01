from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class PublishJobRepository:
    table_name = "publish_jobs"
    columns = (
        "id,campaign_id,revision_id,schedule_id,status,action,shopify_resource_type,shopify_resource_id,"
        "request_payload,response_payload,error_message,idempotency_key,started_at,finished_at,created_at"
    )
    writable_columns = {
        "campaign_id",
        "revision_id",
        "schedule_id",
        "status",
        "action",
        "shopify_resource_type",
        "shopify_resource_id",
        "request_payload",
        "response_payload",
        "error_message",
        "idempotency_key",
        "started_at",
        "finished_at",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def get_by_idempotency_key(self, *, idempotency_key: str) -> dict[str, Any] | None:
        out = execute_data(self.client.table(self.table_name).select(self.columns).eq("idempotency_key", idempotency_key).limit(1))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None

    def create_or_get(self, *, data: dict[str, Any]) -> dict[str, Any]:
        idempotency_key = data.get("idempotency_key")
        if idempotency_key:
            existing = self.get_by_idempotency_key(idempotency_key=str(idempotency_key))
            if existing:
                return existing
        return self.create(data=data)

    def update(self, *, job_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).update(payload).eq("id", job_id).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else None
        return dict(out) if out else None
