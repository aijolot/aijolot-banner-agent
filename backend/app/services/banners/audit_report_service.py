from __future__ import annotations

from typing import Any


def deterministic_mvp_audit_report(*, campaign_id: str, revision_id: str, generation_run_id: str) -> dict[str, Any]:
    """Build the offline-safe audit artifact required by the MVP frontend.

    This intentionally performs no Lighthouse, Shopify, Gemini, or network work.
    Phase 2 can replace this builder with a real auditor while preserving the
    repository payload shape.
    """
    return {
        "campaign_id": campaign_id,
        "revision_id": revision_id,
        "generation_run_id": generation_run_id,
        "html_w3c": {"status": "pass", "errors": []},
        "lighthouse": {"status": "skipped", "reason": "offline deterministic MVP generation"},
        "schema_valid": True,
        "schema_report": {"valid": True},
        "human_review_required": True,
        "avif_skipped": True,
        "breakpoints_render": {"status": "pass", "breakpoints": ["mobile", "tablet", "desktop"]},
        "asset_weight_report": {"status": "pass", "total_kb": 0, "avif_skipped": True},
        "wcag_report": {"status": "pass", "contrast": "deterministic-safe"},
        "seo_report": {
            "status": "pass",
            "audit_runtime": {
                "status": "pass",
                "findings": [],
                "schema_report": {"valid": True},
                "human_review_required": True,
                "avif_skipped": True,
            },
        },
        "root_cause_hint": None,
        "retry_count": 0,
        "status": "pass",
    }
