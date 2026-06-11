"""banner-concept-draft skill."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.agents.state import BannerSessionState, Campaign, Concept, Variant
from app.agents.tools import gemini_text
from app.schemas.brand import BrandContext
from app.services.brands.color_roles import choose_role_color
from app.services.brands.font_roles import font_aesthetic_hint, font_prompt_lines

EST_CONCEPT_COPY_USD = 0.002


class _ConceptCopy(BaseModel):
    """Structured banner copy for the Gemini generation call."""

    eyebrow: str = Field(default="", description="Short kicker, <=4 words")
    headline: str = Field(default="", description="Punchy benefit-led headline, <=8 words")
    subheadline: str = Field(default="", description="One supporting line, <=16 words")
    cta: str = Field(default="", description="Action-first CTA, <=5 words")
    theme_note: str = Field(default="", description="One-line visual scene/theme summary for the user, <=18 words")
    image_concept: str = Field(
        default="",
        description="ENGLISH visual scene for the image generator, <=40 words: concrete subjects, setting, season/event cues that express the campaign goal",
    )


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


def _placement_tokens(placement: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9]+", str(placement or "").lower()) if len(tok) > 2}


def _resolve_layout(
    *,
    layout_candidates: list[dict[str, Any]] | None,
    placement: str,
    fallback_layout: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Ground the layout in a KG ``liquid_pattern`` doc when one is available.

    Picks the candidate whose category/applicable_when best matches the
    placement, falling back to the top-ranked candidate, then to the
    deterministic layout string when retrieval returned nothing.
    """
    candidates = [c for c in (layout_candidates or []) if c.get("title")]
    if not candidates:
        return fallback_layout, []

    placement_tokens = _placement_tokens(placement)

    def _match_score(doc: dict[str, Any]) -> int:
        meta = doc.get("metadata") or {}
        haystack = f"{meta.get('category', '')} {meta.get('applicable_when', '')}".lower()
        return sum(1 for tok in placement_tokens if tok in haystack)

    ranked = sorted(candidates, key=lambda d: (-_match_score(d), -float(d.get("score") or 0.0)))
    chosen = ranked[0]
    meta = chosen.get("metadata") or {}
    applicable = str(meta.get("applicable_when") or "").strip()
    title = str(chosen.get("title") or "Layout pattern").strip()
    layout = _truncate(f"{title} — {applicable}" if applicable else title, 200)

    source_refs = [
        {
            "kind": str(doc.get("kind") or "liquid_pattern"),
            "id": doc.get("id"),
            "title": str(doc.get("title") or ""),
            "category": (doc.get("metadata") or {}).get("category"),
            "applicable_when": (doc.get("metadata") or {}).get("applicable_when"),
            "score": doc.get("score"),
            "selected": doc is chosen,
        }
        for doc in ranked
    ]
    return layout, source_refs


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
    layout_candidates: list[dict[str, Any]] | None = None,
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

    primary = choose_role_color(brand_context, "primary", "main identity text visual anchor")
    secondary = choose_role_color(brand_context, "secondary", "support background surface")
    accent = choose_role_color(brand_context, "tertiary", "cta accent button highlight")
    cta_text = choose_role_color(brand_context, "secondary", "text foreground on cta")

    variant_notes = []
    for variant in variants or []:
        variant_notes.append(f"{variant.customer_tag}: {variant.intent_delta}")

    practice_notes = [doc.get("title", "") for doc in (best_practices or [])[:3] if doc.get("title")]
    fold = _get(art_direction, "fold_percentage", 55)
    background_mode = _get(art_direction, "background_mode", "hero")

    fallback_layout = f"{placement} split layout: copy block left, product/visual right, focal area safe within {fold}% fold"
    layout, source_refs = _resolve_layout(
        layout_candidates=layout_candidates,
        placement=placement,
        fallback_layout=fallback_layout,
    )
    layout_note = [f"KG layout: {source_refs[0]['title']}"] if source_refs else []
    # Approved/legacy brand fonts guide the HTML/Liquid copy layers (never the
    # generated image pixels, which stay text-free).
    font_lines = font_prompt_lines(brand_context)
    typography_note = [f"Typography: {', '.join(font_lines)}"] if font_lines else []
    hierarchy_notes = "; ".join(
        [
            "One headline, one support line, one CTA",
            f"Audience rationale: {audience}",
            *layout_note,
            *(variant_notes[:2] or []),
            *(practice_notes[:2] or []),
            *typography_note,
        ]
    )

    safe_catalog_line = _sanitize_image_fragment(catalog_line)
    # Category-level vibe only (e.g. "geometric sans-serif aesthetic"): font names
    # never enter the image prompt because generated pixels must stay text-free.
    font_hint = _sanitize_image_fragment(font_aesthetic_hint(brand_context))
    image_prompt = ", ".join(
        part for part in [
            _sanitize_image_fragment(f"{background_mode} ecommerce banner background"),
            safe_catalog_line or "featured product scene",
            # Ground the deterministic prompt in the brief too — the image must
            # express the campaign, not just the product (Gemini replaces this
            # with a richer image_concept when available).
            _sanitize_image_fragment(f"campaign theme: {_truncate(goal, 80)}") if goal else "",
            f"brand color roles {_sanitize_image_fragment(primary['label'])} primary anchor and {_sanitize_image_fragment(secondary['label'])} secondary support",
            font_hint,
            # Safety (mark-free/people-free) is appended by image-prompt-refine's
            # un-truncatable suffix — repeating it here only eats word budget.
            "clean negative space for later HTML copy and product focus",
        ] if part
    )

    return Concept(
        layout=layout,
        copy={
            "headline": headline,
            "subheadline": subcopy,
            "cta": _truncate(_remove_prohibited(cta, prohibited_words) or "Shop now", 40),
            "audience": _remove_prohibited(audience, prohibited_words),
            "rationale": _remove_prohibited(f"Connects {goal} to {audience} with {urgency} urgency.", prohibited_words),
        },
        palette_usage={
            "background": secondary["token"],
            "text": primary["token"],
            "cta_background": accent["token"],
            "cta_text": cta_text["token"],
        },
        image_prompt=image_prompt,
        hierarchy_notes=hierarchy_notes,
        source_refs=source_refs,
    )


def _product_lines(catalog_context: Any) -> str:
    items = _get(catalog_context, "items", []) or []
    titles = []
    for item in items[:4]:
        title = _get(item, "title", "")
        if title:
            titles.append(str(title))
    return "; ".join(titles)


def _campaign_lang_name(campaign: Any) -> str:
    from app.core.i18n import campaign_lang, lang_name

    brief = _brief(campaign)
    explicit = brief.get("language") if isinstance(brief, dict) else getattr(brief, "language", None)
    if explicit:
        return lang_name(str(explicit))
    # Fallback heurístico solo cuando la campaña no trae idioma explícito.
    goal = str(_get(brief, "goal", "")); audience = str(_get(brief, "audience", ""))
    return "Spanish (Mexico)" if re.search(r"[áéíóúñ¿¡]|\b(de|para|con|los|las|promo)\b", f"{goal} {audience}", re.I) else "English"


def _build_copy_prompt(*, campaign: Any, brand_context: BrandContext, catalog_context: Any, best_practices: list[dict[str, Any]] | None, layout_hint: str, audience_override: str = "", refine_instruction: str = "") -> str:
    brief = _brief(campaign)
    goal = _get(brief, "goal", "")
    audience = audience_override or _get(brief, "audience", "")
    tone = _get(brief, "tone", "") or ", ".join(brand_context.voice.tone)
    urgency = _get(brief, "urgency", "")
    cta = _get(brief, "cta", "")
    products = _product_lines(catalog_context)
    practices = "; ".join([str(d.get("title", "")) for d in (best_practices or [])[:4] if d.get("title")])
    required = ", ".join(brand_context.voice.required_phrases or [])
    prohibited = ", ".join(brand_context.voice.prohibited_words or [])
    lang = _campaign_lang_name(campaign)
    return (
        "You are a senior ecommerce copywriter. Write ONE banner's hero copy.\n"
        f"CAMPAIGN GOAL (this is the THEME — the copy, theme_note and image_concept MUST visibly express it; "
        f"products support the goal, never replace it): {goal}\n"
        f"Audience: {audience}\nTone: {tone}\nUrgency: {urgency}\n"
        f"Offer / CTA seed: {cta}\nFeatured products: {products or 'the featured catalog'}\n"
        f"Layout direction: {layout_hint}\n"
        f"Best-practice notes from our knowledge base: {practices or 'standard ecommerce banner hierarchy'}\n"
        f"Brand required phrases: {required or 'none'}\nProhibited words (never use): {prohibited or 'none'}\n\n"
        f"Write in {lang}. Be specific to the products and the offer — not generic. "
        "If the goal names an event, season or moment (e.g. a World Cup, a holiday, same-day delivery), "
        "the headline and image_concept must reference it concretely. "
        "One headline (<=8 words, benefit-led, may reference the product/season), one short eyebrow (<=4 words), "
        "one supporting subheadline (<=16 words), one action-first CTA (<=5 words), "
        f"and one theme_note: a one-line summary (<=18 words, in {lang}) of the visual scene/theme the banner will convey. "
        "Also return image_concept (ALWAYS in English, <=40 words): the concrete visual scene the banner IMAGE should "
        "show — subjects, setting, props and season/event cues that genuinely express the campaign goal and offer "
        "(e.g. a World Cup campaign needs football/celebration cues, a same-day-delivery promo needs motion/urgency cues). "
        "Describe a scene, not abstract style words. NEVER write text/letters/logos into the scene. "
        "No clickbait, no prohibited words, no emojis. Return JSON matching the schema."
        + (
            f"\n\nUSER REFINEMENT FEEDBACK (MUST be addressed in the rewrite, in the user's language): \"{refine_instruction}\". "
            "Apply it to the relevant fields and keep everything else consistent with the brief."
            if refine_instruction
            else ""
        )
    )


async def _gemini_copy(*, campaign: Any, brand_context: BrandContext, catalog_context: Any, best_practices: list[dict[str, Any]] | None, layout_hint: str, settings: Any, cost_guard: Any, audience_override: str = "", refine_instruction: str = "") -> dict[str, str] | None:
    if settings is None or not getattr(settings, "has_google_api_key", lambda: False)():
        return None
    try:
        from app.services.gemini.cost_guard import get_default_cost_guard

        guard = cost_guard or get_default_cost_guard(settings)
        if not guard.check_and_reserve(EST_CONCEPT_COPY_USD).allowed:
            return None
        result = await gemini_text.generate(
            _build_copy_prompt(campaign=campaign, brand_context=brand_context, catalog_context=catalog_context, best_practices=best_practices, layout_hint=layout_hint, audience_override=audience_override, refine_instruction=refine_instruction),
            model=gemini_text.FLASH_MODEL,
            structured=_ConceptCopy,
        )
    except gemini_text.GeminiUnavailable:
        return None
    except Exception:  # noqa: BLE001 — any failure → deterministic copy
        return None
    prohibited = brand_context.voice.prohibited_words or []
    out: dict[str, str] = {}
    for key, limit in (("eyebrow", 32), ("headline", 60), ("subheadline", 120), ("cta", 40), ("theme_note", 160), ("image_concept", 320)):
        value = _remove_prohibited(str(_get(result, key, "")), prohibited)
        if value:
            out[key] = _truncate(value, limit)
    return out or None


async def copy_for_audience(
    *,
    campaign: Any,
    brand_context: BrandContext,
    catalog_context: Any = None,
    best_practices: list[dict[str, Any]] | None = None,
    layout_hint: str = "",
    audience: str,
    settings: Any = None,
    cost_guard: Any = None,
) -> dict[str, str]:
    """Variant-specific banner copy for one audience (F11 — N variants by tag).

    Deterministic base (audience-overridden) refined by Gemini when available.
    Returns {eyebrow, headline, subheadline, cta}.
    """
    brief = _brief(campaign)
    overridden = {
        "goal": _get(brief, "goal", ""), "audience": audience or _get(brief, "audience", ""),
        "cta": _get(brief, "cta", ""), "tone": _get(brief, "tone", ""),
        "urgency": _get(brief, "urgency", ""), "placement": _get(brief, "placement", ""),
        "language": _get(brief, "language", ""),
    }
    base = draft_concept(campaign=overridden, brand_context=brand_context, best_practices=best_practices, catalog_context=catalog_context)
    copy = {k: base.copy.get(k, "") for k in ("eyebrow", "headline", "subheadline", "cta")}
    copy["eyebrow"] = copy.get("eyebrow") or (audience or "").upper()[:32]
    gem = await _gemini_copy(
        campaign=overridden, brand_context=brand_context, catalog_context=catalog_context,
        best_practices=best_practices, layout_hint=layout_hint or base.layout,
        settings=settings, cost_guard=cost_guard, audience_override=audience,
    )
    if gem:
        copy.update({k: v for k, v in gem.items() if v})
    return copy


async def run(
    state: BannerSessionState | None = None,
    *,
    campaign: Campaign | dict[str, Any] | None = None,
    brand_context: BrandContext | None = None,
    variants: list[Variant] | None = None,
    best_practices: list[dict[str, Any]] | None = None,
    layout_candidates: list[dict[str, Any]] | None = None,
    placement_context: Any = None,
    catalog_context: Any = None,
    art_direction: Any = None,
    settings: Any = None,
    cost_guard: Any = None,
    refine_instruction: str = "",
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
    concept = draft_concept(
        campaign=campaign,
        brand_context=brand_context,
        variants=variants,
        best_practices=best_practices,
        layout_candidates=layout_candidates,
        placement_context=placement_context,
        catalog_context=catalog_context,
        art_direction=art_direction,
    )
    # Quality jump: replace the deterministic template copy with Gemini-written,
    # product- and offer-specific banner copy when a key + budget are available.
    gem = await _gemini_copy(
        campaign=campaign, brand_context=brand_context, catalog_context=catalog_context,
        best_practices=best_practices, layout_hint=concept.layout, settings=settings, cost_guard=cost_guard,
        refine_instruction=refine_instruction,
    )
    if gem:
        for key in ("eyebrow", "headline", "subheadline", "cta", "theme_note"):
            if gem.get(key):
                concept.copy[key] = gem[key]
        concept.copy["copy_source"] = "gemini"
        # The model's brief-grounded scene REPLACES the deterministic catalog/palette
        # image prompt — this is what makes the generated image reflect the campaign
        # theme (e.g. World Cup, same-day delivery) instead of a generic product mood.
        if gem.get("image_concept"):
            concept.image_prompt = _sanitize_image_fragment(gem["image_concept"]) or concept.image_prompt
    return concept
