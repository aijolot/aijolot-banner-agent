from __future__ import annotations

import math
import re
from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class KGDocumentRepository:
    """Supabase repository for public.kg_documents.

    Task 11 uses deterministic/static retrieval by default; this repository is a
    thin adapter for the already-present KG table so later embedding-backed work
    can plug in without changing skill contracts.
    """

    table_name = "kg_documents"
    columns = "id,kind,title,body,metadata,brand_id,created_at,updated_at"
    writable_columns = {"kind", "title", "body", "metadata", "embedding", "brand_id"}
    _safe_brand_id_re = re.compile(
        r"^(?:[A-Za-z0-9][A-Za-z0-9_-]{0,127}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
    )

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def list(
        self,
        *,
        kinds: list[str] | None = None,
        brand_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if brand_id and not self._safe_brand_id_re.fullmatch(brand_id):
            raise ValueError("brand_id contains unsafe characters")
        query = self.client.table(self.table_name).select(self.columns)
        if kinds:
            query = query.in_("kind", kinds)
        if brand_id:
            query = query.or_(f"brand_id.is.null,brand_id.eq.{brand_id}")
        data = execute_data(query.order("updated_at", desc=True).limit(limit))
        return [dict(row) for row in (data or [])]

    def insert(self, *, data: dict[str, Any]) -> dict[str, Any]:
        brand_id = data.get("brand_id")
        if brand_id and not self._safe_brand_id_re.fullmatch(str(brand_id)):
            raise ValueError("brand_id contains unsafe characters")
        embedding = data.get("embedding")
        if not isinstance(embedding, list) or len(embedding) != 768:
            raise ValueError("embedding must be present and have dimension 768")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in embedding):
            raise ValueError("embedding values must be finite numbers")
        payload = {key: value for key, value in data.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})
