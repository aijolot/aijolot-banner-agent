"""banner-concept-draft skill."""

from __future__ import annotations

import re
from typing import Any

from app.agents.state import BannerSessionState, Campaign, Concept, Variant
from app.schemas.brand import BrandContext


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _brief(campaign: Any) -> Any:
    return _get(campaign, "structured_brief", campaign)


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _remove_prohibited(text: str, prohibited_words: list[str]) -> str:
    cleaned = str(text or "")
    for word in prohibited_words:
        token = str(word or "").strip()
        if not token:
            continue
        cleaned = re.sub(rf"\b{re.escape(token)}\b", "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split()).strip(" -·—,:;")

_IMAGE_FORBIDDEN_REPLACEMENTS = {
    "text overlay": "blank copy space",
    "with text": "with blank copy space",
    "no text": "blank copy space",
    "no words": "abstract details only",
    "no letters": "abstract details only",
    "no signage": "clean environmental areas",
    "no captions": "blank copy space",
    "no caption": "blank copy space",
    "no headlines": "blank hero focal area",
    "no headline": "blank hero focal area",
    "no logos": "mark-free brand-safe styling",
    "no logo": "mark-free brand-safe styling",
    "no ui chrome": "clean composition",
    "no ui": "clean composition",
    "no faces": "people-free scene",
    "no face": "people-free scene",
    "typography": "visual rhythm",
    "words": "abstract details",
    "letters": "abstract details",
    "signage": "clean environmental areas",
    "captions": "blank copy space",
    "caption": "blank copy space",
    "headlines": "blank hero focal area",
    "headline": "blank hero focal area",
    "logos": "mark-free brand-safe styling",
    "logo": "mark-free brand-safe styling",
    "ui chrome": "clean composition",
    "ui": "clean composition",
    "faces": "people-free scene",
    "face": "people-free scene",
    "text": "blank copy space",
}


def _sanitize_image_fragment(value: str) -> str:
    cleaned = " ".join(str(value or "").split())
    for old, new in sorted(_IMAGE_FORBIDDEN_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
        cleaned = re.sub(rf"\b{re.escape(old)}\b", new, cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,")


def _append_required_phrase(base: str, phrase: str, limit: int) -> str:
    base = " ".join(str(base or "").split())
    phrase = " ".join(str(phrase or "").split())
    if not phrase or phrase.lower() in base.lower():
        return _truncate(base, limit)
    if len(phrase) >= limit:
        return _truncate(phrase, limit)
    separator = " · "
    available = limit - len(separator) - len(phrase)
    shortened_base = _truncate(base, available) if available > 0 else ""
    return f"{shortened_base}{separator if shortened_base else ''}{phrase}"


def _catalog_summary(catalog_context: Any) -> str:
    items = _get(catalog_context, "items", []) or []
    if not items:
        return ""
    first = items[0]
    title = _get(first, "title", "featured product")
    price = _get(first, "sale_price", None) or _get(first, "price", None)
    return f"Feature {title}" + (f" at {price:g}" if isinstance(price, (int, float)) else "")


def draft_concept(
    *,
    campaign: Campaign | dict[str, Any],
    brand_context: BrandContext,
    variants: list[Variant] | None = None,
    best_practices: list[dict[str, Any]] | None = None,
    placement_context: Any = None,
    catalog_context: Any = None,
    art_direction: Any = None,
) -> Concept:
    brief = _brief(campaign)
    goal = str(_get(brief, "goal", "Promote featured offer") or "Promote featured offer")
    audience = str(_get(brief, "audience", "target shoppers") or "target shoppers")
    cta = str(_get(brief, "cta", "Shop now") or "Shop now")
    tone = str(_get(brief, "tone", "") or ", ".join(brand_context.voice.tone) or "clear")
    urgency = str(_get(brief, "urgency", "medium") or "medium")
    placement = str(_get(brief, "placement", "") or _get(placement_context, "placement_type_key", "hero"))
    catalog_line = _catalog_summary(catalog_context)
    prohibited_words = brand_context.voice.prohibited_words or []

    required_phrase = brand_context.voice.required_phrases[0] if brand_context.voice.required_phrases else ""
    headline_seed = _remove_prohibited(catalog_line or goal, prohibited_words) or "Featured offer"
    headline = _append_required_phrase(headline_seed, _remove_prohibited(required_phrase, prohibited_words), 58)

    subcopy_parts = [f"For {_remove_prohibited(audience, prohibited_words) or 'target shoppers'}"]
    if urgency.lower() in {"high", "urgent"}:
        subcopy_parts.append("limited-time")
    subcopy_parts.append(f"with a {_remove_prohibited(tone.lower(), prohibited_words) or 'clear'} tone")
    subcopy = _truncate(_remove_prohibited(" — ".join(subcopy_parts), prohibited_words), 110)

    primary = brand_context.palette[0]
    secondary = brand_context.palette[1] if len(brand_context.palette) > 1 else brand_context.palette[0]
    accent = brand_context.palette[2] if len(brand_context.palette) > 2 else primary

    variant_notes = []
    for variant in variants or []:
        variant_notes.append(f"{variant.customer_tag}: {variant.intent_delta}")

    practice_notes = [doc.get("title", "") for doc in (best_practices or [])[:3] if doc.get("title")]
    fold = _get(art_direction, "fold_percentage", 55)
    background_mode = _get(art_direction, "background_mode", "hero")

    layout = f"{placement} split layout: copy block left, product/visual right, focal area safe within {fold}% fold"
    hierarchy_notes = "; ".join(
        [
            "One headline, one support line, one CTA",
            f"Audience rationale: {audience}",
            *(variant_notes[:2] or []),
            *(practice_notes[:2] or []),
        ]
    )

    safe_catalog_line = _sanitize_image_fragment(catalog_line)
    image_prompt = ", ".join(
        part for part in [
            _sanitize_image_fragment(f"{background_mode} ecommerce banner background"),
            safe_catalog_line or "featured product scene",
            f"brand palette tokens {_sanitize_image_fragment(primary.name)} and {_sanitize_image_fragment(secondary.name)}",

            "clean negative space for later HTML copy and product focus",
            "mark-free, interface-free, people-free commercial composition",
        ] if part
    )

    return Concept(
        layout=layout,
        copy={
            "headline": headline,
            "subheadline": subcopy,
            "cta": _truncate(_remove_prohibited(cta, prohibited_words) or "Shop now", 28),
            "audience": _remove_prohibited(audience, prohibited_words),
            "rationale": _remove_prohibited(f"Connects {goal} to {audience} with {urgency} urgency.", prohibited_words),
        },
        palette_usage={
            "background": secondary.name,
            "text": primary.name,
            "cta_background": accent.name,
            "cta_text": secondary.name,
        },
        image_prompt=image_prompt,
        hierarchy_notes=hierarchy_notes,
    )


async def run(
    state: BannerSessionState | None = None,
    *,
    campaign: Campaign | dict[str, Any] | None = None,
    brand_context: BrandContext | None = None,
    variants: list[Variant] | None = None,
    best_practices: list[dict[str, Any]] | None = None,
    placement_context: Any = None,
    catalog_context: Any = None,
    art_direction: Any = None,
) -> Concept:
    if state is not None:
        campaign = campaign or state.campaign
        brand_context = brand_context or state.brand_context
        variants = variants if variants is not None else state.variants
        best_practices = best_practices if best_practices is not None else state.best_practices
    if campaign is None:
        raise ValueError("campaign is required")
    if brand_context is None:
        raise ValueError("brand_context is required")
    return draft_concept(
        campaign=campaign,
        brand_context=brand_context,
        variants=variants,
        best_practices=best_practices,
        placement_context=placement_context,
        catalog_context=catalog_context,
        art_direction=art_direction,
    )
