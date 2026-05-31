"""user-personalization skill."""

from __future__ import annotations

import re
from typing import Any

from app.agents.state import Campaign, Variant
from app.schemas.campaign import StructuredBrief


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _brief(campaign: Any) -> Any:
    return _get(campaign, "structured_brief", campaign)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _tags_from_text(text: str) -> list[str]:
    tags: list[str] = []
    lowered = text.lower()
    patterns = {
        "vip": r"\b(vip|loyal|fiel|premium)\b",
        "new_customer": r"\b(new|nuevo|primera compra|first)\b",
        "deal_seeker": r"\b(descuent|discount|sale|black friday|oferta|promo|50%)\b",
        "gift_buyer": r"\b(gift|regalo|holiday|navidad)\b",
        "category_browser": r"\b(collection|colecci[oó]n|category|categor[ií]a)\b",
    }
    for tag, pattern in patterns.items():
        if re.search(pattern, lowered):
            tags.append(tag)
    return tags


async def run(
    campaign: Campaign | StructuredBrief | dict[str, Any],
    *,
    customer_tags: list[str] | None = None,
    context: dict[str, Any] | None = None,
    max_variants: int = 3,
) -> list[Variant]:
    brief = _brief(campaign)
    audience = _clean(_get(brief, "audience", "general shoppers")) or "general shoppers"
    goal = _clean(_get(brief, "goal", "campaign")) or "campaign"
    cta = _clean(_get(brief, "cta", "Shop now")) or "Shop now"
    urgency = _clean(_get(brief, "urgency", "medium")).lower() or "medium"

    requested = ["default"]
    requested.extend(list(customer_tags or []))
    if context:
        requested.extend([str(tag) for tag in context.get("customer_tags", [])])
    requested.extend(_tags_from_text(" ".join([audience, goal, cta])))
    requested.append("primary_audience")

    ordered: list[str] = []
    for tag in requested:
        normalized = re.sub(r"[^a-z0-9_]+", "_", tag.strip().lower()).strip("_")
        if normalized and normalized not in ordered:
            ordered.append(normalized)

    templates: dict[str, tuple[str, dict[str, str]]] = {
        "default": (f"Use the baseline campaign message for {audience} without segment-specific changes.", {"audience": audience, "cta": cta}),
        "primary_audience": (f"Match the core promise to {audience}.", {"audience": audience, "cta": cta}),
        "vip": ("Reward loyalty with early access or elevated value framing.", {"headline_suffix": "for loyal customers", "cta": cta}),
        "new_customer": ("Reduce first-purchase hesitation with clarity and reassurance.", {"headline_suffix": "made easy", "cta": cta}),
        "deal_seeker": ("Lead with savings and urgency while keeping one clear action.", {"headline_prefix": "Limited offer", "cta": cta}),
        "gift_buyer": ("Frame the offer as a timely gift solution.", {"headline_suffix": "gift-ready", "cta": cta}),
        "category_browser": ("Help browsers understand the collection fit quickly.", {"headline_suffix": "picked for you", "cta": cta}),
    }

    variants: list[Variant] = []
    variant_limit = max(1, min(int(max_variants or 1), 4))
    for tag in ordered:
        rationale, overrides = templates.get(tag, (f"Personalize message emphasis for {tag.replace('_', ' ')}.", {"cta": cta}))
        if urgency in {"high", "urgent"}:
            overrides = {**overrides, "urgency": "Act now"}
        variants.append(Variant(customer_tag=tag, intent_delta=rationale, copy_override=overrides))
        if len(variants) >= variant_limit:
            break
    return variants
