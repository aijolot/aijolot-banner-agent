"""best-practices-retrieve skill."""

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


async def run(campaign: Any, brand_context: Any, *, top_k: int = 5) -> list[dict[str, Any]]:
    brief = _brief(campaign)
    query = " · ".join(
        part for part in [
            str(_get(brief, "goal", "")),
            f"audience={_get(brief, 'audience', '')}",
            f"tone={_get(brief, 'tone', '')}",
            f"cta={_get(brief, 'cta', '')}",
            f"placement={_get(brief, 'placement', '')}",
            f"urgency={_get(brief, 'urgency', '')}",
            " ".join(getattr(getattr(brand_context, "voice", None), "tone", []) or []),
        ] if part
    )
    return await kg.retrieve(
        query,
        kinds=["best_practice", "brand_example", "prior_banner"],
        brand_id=_get(brand_context, "id", _get(brand_context, "brand_id", None)),
        top_k=top_k,
    )
