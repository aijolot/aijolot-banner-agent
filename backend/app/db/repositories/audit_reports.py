from __future__ import annotations

from typing import Any

from app.db.repositories._supabase import SupabaseClient, execute_data


class AuditReportRepository:
    """Thin Supabase adapter for public.audit_reports."""

    table_name = "audit_reports"
    columns = (
        "id,campaign_id,revision_id,generation_run_id,html_w3c,lighthouse,schema_valid,"
        "breakpoints_render,asset_weight_report,wcag_report,seo_report,root_cause_hint,"
        "retry_count,status,created_at"
    )
    writable_columns = {
        "campaign_id",
        "revision_id",
        "generation_run_id",
        "html_w3c",
        "lighthouse",
        "schema_valid",
        "breakpoints_render",
        "asset_weight_report",
        "wcag_report",
        "seo_report",
        "root_cause_hint",
        "retry_count",
        "status",
    }

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_for_storage(data)
        payload = {key: value for key, value in normalized.items() if key in self.writable_columns and value is not None}
        out = execute_data(self.client.table(self.table_name).insert(payload).select(self.columns))
        if isinstance(out, list):
            return dict(out[0]) if out else {}
        return dict(out or {})

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("campaign_id", campaign_id)
            .order("created_at", desc=True)
            .limit(1)
        )
        if isinstance(out, list):
            return self._enrich_row(dict(out[0])) if out else None
        return self._enrich_row(dict(out)) if out else None

    def list_by_revision_id(self, *, revision_id: str) -> list[dict[str, Any]]:
        out = execute_data(
            self.client.table(self.table_name)
            .select(self.columns)
            .eq("revision_id", revision_id)
            .order("created_at", desc=True)
        )
        return [self._enrich_row(dict(row)) for row in (out or [])]

    @staticmethod
    def _normalize_for_storage(data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        runtime_status = str(normalized.get("status") or "pending")
        if runtime_status == "warn":
            normalized["status"] = "pass"
        elif runtime_status not in {"pending", "pass", "fail", "escalated"}:
            normalized["status"] = "escalated"

        asset_report = dict(normalized.get("asset_weight_report") or {})
        if "avif_skipped" in normalized:
            asset_report["avif_skipped"] = bool(normalized.get("avif_skipped"))
        normalized["asset_weight_report"] = asset_report

        seo_report = dict(normalized.get("seo_report") or {})
        seo_report["audit_runtime"] = {
            "status": runtime_status,
            "findings": normalized.get("findings") or [],
            "schema_report": normalized.get("schema_report") or {},
            "human_review_required": bool(normalized.get("human_review_required", True)),
            "avif_skipped": bool(normalized.get("avif_skipped", False)),
        }
        normalized["seo_report"] = seo_report
        return normalized

    @staticmethod
    def _enrich_row(row: dict[str, Any]) -> dict[str, Any]:
        runtime = ((row.get("seo_report") or {}).get("audit_runtime") or {}) if isinstance(row.get("seo_report"), dict) else {}
        row.setdefault("runtime_status", runtime.get("status", row.get("status")))
        row.setdefault("findings", runtime.get("findings", []))
        row.setdefault("schema_report", runtime.get("schema_report", {}))
        row.setdefault("human_review_required", runtime.get("human_review_required", True))
        row.setdefault("avif_skipped", runtime.get("avif_skipped", bool((row.get("asset_weight_report") or {}).get("avif_skipped") if isinstance(row.get("asset_weight_report"), dict) else False)))
        return row
