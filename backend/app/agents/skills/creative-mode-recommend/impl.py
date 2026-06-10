"""creative-mode-recommend skill (C0).

Recommend composite | full_picture | video + include_humans from the brief and
brand context. Gemini FLASH structured when available; deterministic vertical
keyword rules otherwise. Video is hard-gated behind settings.video_generation_enabled.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.tools import gemini_text
from app.schemas.creative_mode import CreativeModeRecommendation

EST_RECOMMEND_USD = 0.001

# Verticals where a generated full scene (and people) sell better than a cut-out.
_FULL_PICTURE_HINTS = (
    "moda", "fashion", "ropa", "apparel", "outfit", "beauty", "belleza", "skincare", "maquillaje",
    "makeup", "perfume", "fragancia", "fragrance", "lifestyle", "fitness", "yoga", "joyería",
    "joyeria", "jewelry", "viaje", "travel", "spa", "wellness",
)
# People-led verticals (subset of the above minus product-only ones like perfume bottles).
_HUMANS_HINTS = (
    "moda", "fashion", "ropa", "apparel", "outfit", "beauty", "belleza", "skincare", "maquillaje",
    "makeup", "fitness", "yoga", "joyería", "joyeria", "jewelry", "lifestyle", "modelo", "model",
)
# Product-led / technical verticals → composite cut-out, no people.
_COMPOSITE_HINTS = (
    "ferretería", "ferreteria", "herramienta", "tools", "electrónica", "electronica", "electronics",
    "refacciones", "autopartes", "b2b", "industrial", "software", "gadget", "hardware",
)
_VIDEO_HINTS = ("video", "motion", "animado", "animated", "lanzamiento", "launch", "teaser")
_HERO_PLACEMENTS = ("hero", "home")


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        brief = obj.get("structured_brief")
        if isinstance(brief, dict) and key in brief:
            return brief.get(key, default)
        return obj.get(key, default)
    return getattr(obj, key, default)


def _campaign_text(campaign: Any, brand_context: Any) -> str:
    parts = [
        str(_get(campaign, "goal", "")),
        str(_get(campaign, "audience", "")),
        str(_get(campaign, "tone", "")),
        str(_get(campaign, "placement", "")),
    ]
    products = _get(campaign, "products", []) or []
    for product in products if isinstance(products, list) else []:
        parts.append(str((product or {}).get("product_title") if isinstance(product, dict) else product))
    notes = getattr(brand_context, "notes", "") or ""
    parts.append(str(notes)[:200])
    return " ".join(p for p in parts if p).lower()


def _hits(text: str, tokens: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<![\w]){re.escape(t)}", text) for t in tokens)


def fallback_recommendation(campaign: Any, brand_context: Any, *, placement: str = "", settings: Any = None) -> CreativeModeRecommendation:
    """Deterministic vertical-keyword rules (demo-safe, no LLM)."""
    text = _campaign_text(campaign, brand_context)
    placement_text = (placement or str(_get(campaign, "placement", ""))).lower()
    video_enabled = bool(getattr(settings, "video_generation_enabled", False))

    if video_enabled and _hits(text, _VIDEO_HINTS) and _hits(placement_text, _HERO_PLACEMENTS):
        return CreativeModeRecommendation(
            creative_mode="video", include_humans=_hits(text, _HUMANS_HINTS),
            rationale="El brief pide motion/lanzamiento en un hero principal y la generación de video está habilitada.",
            source="deterministic",
        )
    if _hits(text, _COMPOSITE_HINTS):
        return CreativeModeRecommendation(
            creative_mode="composite", include_humans=False,
            rationale="Vertical orientado a producto/técnico: el recorte de producto sobre fondo de marca comunica mejor.",
            source="deterministic",
        )
    if _hits(text, _FULL_PICTURE_HINTS):
        return CreativeModeRecommendation(
            creative_mode="full_picture", include_humans=_hits(text, _HUMANS_HINTS),
            rationale="Vertical lifestyle/moda: una escena completa generada vende el mood mejor que un recorte.",
            source="deterministic",
        )
    return CreativeModeRecommendation(
        creative_mode="composite", include_humans=False,
        rationale="Sin señales de lifestyle en el brief: recorte de producto (modo seguro por defecto).",
        source="deterministic",
    )


def _build_prompt(campaign: Any, brand_context: Any, placement: str, video_enabled: bool) -> str:
    return (
        "You are an ecommerce creative director choosing the production mode for ONE Shopify banner.\n"
        f"Campaign goal: {_get(campaign, 'goal', '')}\nAudience: {_get(campaign, 'audience', '')}\n"
        f"Tone: {_get(campaign, 'tone', '')}\nPlacement: {placement or _get(campaign, 'placement', '')}\n"
        f"Products: {', '.join(str((p or {}).get('product_title', '')) for p in (_get(campaign, 'products', []) or []) if isinstance(p, dict))}\n"
        f"Brand notes: {str(getattr(brand_context, 'notes', '') or '')[:200]}\n\n"
        "Modes:\n"
        "- composite: real product cut-out over an AI background (product-led promos, hardware, electronics, B2B).\n"
        "- full_picture: a fully AI-generated lifestyle/editorial scene, full-bleed, only text+CTA overlaid "
        "(fashion, beauty, fragrance, lifestyle moods).\n"
        + ("- video: a short looping clip as the hero background — pick ONLY if motion clearly adds value "
           "for a main hero placement (it is expensive).\n" if video_enabled else "")
        + "\nAlso decide include_humans: true only when people genuinely sell this vertical (fashion/beauty/"
        "fitness/jewelry); false for tools, electronics, packaged goods.\n"
        "Return JSON {creative_mode, include_humans, rationale} — rationale: ONE sentence in Spanish."
    )


async def recommend(
    campaign: Any,
    brand_context: Any,
    *,
    placement: str = "",
    settings: Any = None,
    cost_guard: Any = None,
) -> CreativeModeRecommendation:
    fallback = fallback_recommendation(campaign, brand_context, placement=placement, settings=settings)
    if settings is None or not getattr(settings, "has_google_api_key", lambda: False)():
        return fallback
    try:
        from app.services.gemini.cost_guard import get_default_cost_guard

        guard = cost_guard or get_default_cost_guard(settings)
        if not guard.check_and_reserve(EST_RECOMMEND_USD).allowed:
            return fallback
        result = await gemini_text.generate(
            _build_prompt(campaign, brand_context, placement, bool(getattr(settings, "video_generation_enabled", False))),
            model=gemini_text.FLASH_MODEL,
            structured=CreativeModeRecommendation,
        )
    except gemini_text.GeminiUnavailable:
        return fallback
    except Exception:  # noqa: BLE001 — any failure → deterministic rules
        return fallback
    if not isinstance(result, CreativeModeRecommendation):
        return fallback
    # Hard gate: never let the model pick video when it's disabled.
    if result.creative_mode == "video" and not getattr(settings, "video_generation_enabled", False):
        result = CreativeModeRecommendation(
            creative_mode=fallback.creative_mode, include_humans=result.include_humans,
            rationale=result.rationale, source="gemini",
        )
    else:
        result = CreativeModeRecommendation(
            creative_mode=result.creative_mode, include_humans=result.include_humans,
            rationale=(result.rationale or "")[:280], source="gemini",
        )
    return result
