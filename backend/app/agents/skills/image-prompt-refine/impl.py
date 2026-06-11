"""image-prompt-refine skill."""

from __future__ import annotations

import re
from typing import Any

from app.agents.state import Concept
from app.services.brands.color_roles import color_system_prompt_lines
from app.services.brands.font_roles import font_aesthetic_hint

# Replacements that ALWAYS apply (text/logos/UI never belong inside the image).
_FORBIDDEN_REPLACEMENTS = {
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
    "text overlay": "blank copy space",
    "with text": "with blank copy space",
    "typography": "visual rhythm",
    "words": "abstract details",
    "letters": "abstract details",
    "signage": "clean environmental areas",
    "captions": "blank copy space",
    "caption": "blank copy space",
    "headlines": "blank hero focal area",
    "headline": "blank hero focal area",
    "buttons": "commerce-neutral shapes",
    "button": "commerce-neutral shape",
    "modals": "clean composition",
    "modal": "clean composition",
    "screens": "abstract display-free areas",
    "screen": "abstract display-free area",
    "logos": "mark-free brand-safe styling",
    "logo": "mark-free brand-safe styling",
    "ui chrome": "clean composition",
    "ui": "clean composition",
    "text": "blank copy space",
}

# People-related replacements: applied ONLY when humans are NOT allowed (C3).
_PEOPLE_REPLACEMENTS = {
    "no faces": "people-free scene",
    "no face": "people-free scene",
    "faces": "people-free scene",
    "face": "people-free scene",
}

# Responsible-representation directive used when include_humans=True (C3):
# never celebrities, never minors, diverse and non-sexualized casting.
_HUMANS_DIRECTIVE = (
    "adult models only (clearly 21+), no celebrity or public-figure likeness, no minors, "
    "natural diverse casting across skin tones and body types, respectful non-sexualized "
    "styling, photorealistic with honest skin texture"
)


def _forbidden_replacements(include_humans: bool) -> dict[str, str]:
    if include_humans:
        return _FORBIDDEN_REPLACEMENTS
    return {**_FORBIDDEN_REPLACEMENTS, **_PEOPLE_REPLACEMENTS}


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if str(item).strip()]


def _sanitize_list(values: list[str], *, include_humans: bool = False) -> list[str]:
    return [sanitized for value in values if (sanitized := _sanitize(value, include_humans=include_humans))]


def _sanitize(prompt: str, *, include_humans: bool = False) -> str:
    prompt = " ".join(str(prompt or "").split())
    replacements = _forbidden_replacements(include_humans)
    for old, new in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        prompt = re.sub(rf"\b{re.escape(old)}\b", new, prompt, flags=re.IGNORECASE)
    return prompt.strip(" ,")


def _copy_zone_instruction(layout: Any) -> str:
    """C1 — tell the model WHERE the HTML copy will sit so the generated scene
    keeps that zone visually calm (derived from the percent layout, not a vague
    'blank copy space')."""
    text_x = _get(layout, "textX", 6)
    text_w = _get(layout, "textW", 48)
    try:
        center = float(text_x) + float(text_w) / 2.0
    except (TypeError, ValueError):
        center = 30.0
    if center < 38:
        zone = "the LEFT third of the frame"
    elif center > 62:
        zone = "the RIGHT third of the frame"
    else:
        zone = "the CENTER band of the frame"
    return (
        f"Keep {zone} visually calm and uncluttered — low detail, soft even contrast, no focal elements there — "
        "because the headline and CTA will be overlaid in HTML on that area; place the subject and visual interest "
        "in the remaining space."
    )


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _truncate_words(text: str, limit: int) -> str:
    words = str(text or "").split()
    return " ".join(words[:limit]) if len(words) > limit else " ".join(words)


def _single_paragraph(parts: list[str]) -> str:
    return " ".join(" ".join(part.split()) for part in parts if str(part).strip())


async def run(
    concept_or_prompt: Concept | dict[str, Any] | str,
    image_style_directives: str | list[str] | None = None,
    *,
    brand_context: Any = None,
    art_direction: Any = None,
    catalog_context: Any = None,
) -> str:
    """Return a safe structured prompt string for image generation.

    This does not call an image model. Marketing copy remains outside imagery and
    should be rendered later in HTML/Liquid.
    """
    if isinstance(concept_or_prompt, str):
        base = concept_or_prompt
        layout = ""
    else:
        base = str(_get(concept_or_prompt, "image_prompt", ""))
        layout = str(_get(concept_or_prompt, "layout", ""))

    creative_mode = str(_get(art_direction, "creative_mode", "") or "composite")
    include_humans = bool(_get(art_direction, "include_humans", False))
    full_picture = creative_mode in ("full_picture", "video")

    brand_styles = _sanitize_list(_as_list(image_style_directives), include_humans=include_humans)
    color_role_lines: list[str] = []
    font_hint = ""
    if brand_context is not None:
        brand_styles.extend(_sanitize_list(_as_list(_get(brand_context, "image_style_directives", [])), include_humans=include_humans))
        color_role_lines = color_system_prompt_lines(brand_context)
        # Display-font CATEGORY vibe only; font names stay out of image prompts and
        # the no-text rules below remain untouched.
        font_hint = font_aesthetic_hint(brand_context)
        palette = _get(brand_context, "palette", []) or []
        colors = [getattr(color, "hex", None) or (color.get("hex") if isinstance(color, dict) else None) for color in palette]
        colors = [color for color in colors if color]
    else:
        colors = []

    items = _get(catalog_context, "items", []) or []
    product = _get(items[0], "title", "") if items else ""
    background_mode = _get(art_direction, "background_mode", "")
    fold = _get(art_direction, "fold_percentage", None)

    if full_picture:
        # C1 — the model generates the ENTIRE scene (no chroma, no compositing);
        # only text + CTA are overlaid in HTML, on the zone we keep calm.
        layout_spec = _get(art_direction, "layout", {}) or {}
        prompt_parts = [
            "Create a 16:9 FULL-BLEED, edge-to-edge cinematic ecommerce hero scene featuring "
            + _sanitize(base or product or "a premium lifestyle moment", include_humans=include_humans) + ".",
            "The image IS the finished banner background: a complete, art-directed scene with real environment, "
            "natural depth and editorial lighting — not an isolated product on a plain backdrop.",
            _copy_zone_instruction(layout_spec),
        ]
        style_default = "premium editorial commercial photography"
    else:
        # Composite mode: keep the body terse when approved color roles are present
        # so the role directive below survives the word budget.
        base_fragment = _sanitize(base or product or "a product lifestyle scene", include_humans=include_humans)
        layout_fragment = _sanitize(layout, include_humans=include_humans)
        if color_role_lines:
            base_fragment = _truncate_words(base_fragment, 12)
            layout_fragment = _truncate_words(layout_fragment, 12)
        prompt_parts = [
            "Create a 16:9 ecommerce banner background featuring " + base_fragment + ".",
            "Use a responsive composition with generous blank copy space for later HTML-rendered messaging" + (f", informed by {layout_fragment}" if layout_fragment else "") + ".",
        ]
        style_default = "clean commercial ecommerce photography"
    prompt_parts.append("Style it as " + (", ".join(dict.fromkeys(brand_styles)) if brand_styles else style_default) + ".")
    if product:
        prompt_parts.append("Keep the catalog focus on " + _sanitize(product, include_humans=include_humans) + ".")
    if background_mode and not full_picture:
        prompt_parts.append(f"Follow {_sanitize(str(background_mode), include_humans=include_humans)} art direction" + (f" and preserve the focal area inside the {fold}% fold" if fold is not None else "") + ".")
    # Brand + safety constraints are appended AFTER the word-budget truncation so
    # they can never be cut off (the body is what shrinks, not the constraints):
    # approved color roles and the display-font vibe are as load-bearing as the
    # mark-free/people-free safety rules.
    suffix_parts = []
    if color_role_lines:
        suffix_parts.append("Respect approved color roles: " + " | ".join(_sanitize(line) for line in color_role_lines) + ".")
    elif colors:
        suffix_parts.append("Use palette accents: " + ", ".join(colors[:4]) + ".")
    if font_hint:
        suffix_parts.append("Match a " + _sanitize(font_hint) + " in props and composition.")
    if include_humans:
        suffix_parts.append("People may appear naturally in the scene: " + _HUMANS_DIRECTIVE + ".")
    suffix_parts.append(
        "Keep the composition mark-free, symbol-free, interface-free, "
        + ("" if include_humans else "people-free, ")
        + "product-accurate, and brand-safe while avoiding distorted merchandise or unsafe content."
    )
    suffix = _single_paragraph(suffix_parts)
    body_budget = max(30, (160 if full_picture else 120) - _word_count(suffix))

    refined = _single_paragraph(prompt_parts)
    if _word_count(refined) < 40:
        refined += " Keep lighting polished, depth natural, product edges crisp, and negative space uncluttered so the final banner remains accessible and conversion-focused."
    words = refined.split()
    while _word_count(" ".join(words)) > body_budget and words:
        words.pop()
    if _word_count(refined) > body_budget:
        refined = " ".join(words).rstrip(" ,;:") + "."
    return _single_paragraph([refined, suffix])
