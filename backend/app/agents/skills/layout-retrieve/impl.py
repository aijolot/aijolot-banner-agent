"""layout-retrieve skill (F6).

Retrieve `liquid_pattern` layout documents from the Knowledge Graph, ranked for
the campaign's placement/goal/tone, so banner-concept-draft can ground its
layout in evidence-backed Shopify section patterns. Mirrors
best-practices-retrieve but targets the `liquid_pattern` kind.
"""

from __future__ import annotations

from typing import Any

from app.agents.tools import kg


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _brief(campaign: Any) -> Any:
    return _get(campaign, "structured_brief", campaign)


async def run(campaign: Any, brand_context: Any, *, top_k: int = 4) -> list[dict[str, Any]]:
    brief = _brief(campaign)
    placement = str(_get(brief, "placement", "") or "")
    query = " · ".join(
        part
        for part in [
            f"placement={placement}",
            f"layout for {_get(brief, 'goal', '')}",
            f"tone={_get(brief, 'tone', '')}",
            f"audience={_get(brief, 'audience', '')}",
            placement,
        ]
        if part and not part.endswith("=")
    )
    return await kg.retrieve(
        query,
        kinds=["liquid_pattern"],
        brand_id=_get(brand_context, "id", _get(brand_context, "brand_id", None)),
        top_k=top_k,
    )
