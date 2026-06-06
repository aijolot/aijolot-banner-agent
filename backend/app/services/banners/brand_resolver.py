"""Resolve a BrandContext for a persisted campaign row.

Tries the brand store by slug/brand_context_id and falls back to a synthesized
default brand (normalized with conservative defaults) so downstream creative
skills always receive a usable BrandContext, even when the campaign has no
resolvable brand.
"""

from __future__ import annotations

from typing import Any


def resolve_brand_context(campaign_row: dict[str, Any]) -> Any:
    from app.workflows.banner_creation import _load_runtime_skill

    slug = campaign_row.get("brand_slug") or campaign_row.get("brand_context_id")
    if slug:
        try:
            from app.services import brand_store

            return brand_store.get_brand(str(slug))
        except Exception:  # noqa: BLE001 — fall through to synthesized default
            pass
    normalize_brand_context = _load_runtime_skill("brand-context-load").normalize_brand_context
    structured = campaign_row.get("structured_brief") or {}
    tone = structured.get("tone") if isinstance(structured, dict) else None
    return normalize_brand_context(
        {
            "id": str(slug or "default"),
            "name": campaign_row.get("title") or "Default Brand",
            "tone": tone,
        }
    )
