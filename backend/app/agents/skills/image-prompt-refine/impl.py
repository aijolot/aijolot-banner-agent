"""image-prompt-refine skill."""

from __future__ import annotations

import re
from typing import Any

from app.agents.state import Concept
from app.services.brands.color_roles import color_system_prompt_lines
from app.services.brands.font_roles import font_aesthetic_hint

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
    "no faces": "people-free scene",
    "no face": "people-free scene",
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
    "faces": "people-free scene",
    "face": "people-free scene",
    "text": "blank copy space",
}


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


def _sanitize_list(values: list[str]) -> list[str]:
    return [sanitized for value in values if (sanitized := _sanitize(value))]


def _sanitize(prompt: str) -> str:
    prompt = " ".join(str(prompt or "").split())
    for old, new in sorted(_FORBIDDEN_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
        prompt = re.sub(rf"\b{re.escape(old)}\b", new, prompt, flags=re.IGNORECASE)
    return prompt.strip(" ,")


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

    brand_styles = _sanitize_list(_as_list(image_style_directives))
    color_role_lines: list[str] = []
    font_hint = ""
    if brand_context is not None:
        brand_styles.extend(_sanitize_list(_as_list(_get(brand_context, "image_style_directives", []))))
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

    base_fragment = _sanitize(base or product or "a product lifestyle scene")
    if color_role_lines:
        base_fragment = _truncate_words(base_fragment, 12)

    layout_fragment = _sanitize(layout)
    if color_role_lines:
        layout_fragment = _truncate_words(layout_fragment, 12)

    prompt_parts = [
        "Create a 16:9 ecommerce banner background featuring " + base_fragment + ".",
        "Use a responsive composition with generous blank copy space for later HTML-rendered messaging" + (f", informed by {layout_fragment}" if layout_fragment else "") + ".",
    ]
    if color_role_lines:
        prompt_parts.append("Respect approved color roles: " + " | ".join(_sanitize(line) for line in color_role_lines) + ".")
    elif colors:
        prompt_parts.append("Use palette accents: " + ", ".join(colors[:4]) + ".")
    if font_hint:
        prompt_parts.append("Match a " + _sanitize(font_hint) + " in props and composition.")
    prompt_parts.append("Style it as " + (", ".join(dict.fromkeys(brand_styles)) if brand_styles else "clean commercial ecommerce photography") + ".")
    if product:
        prompt_parts.append("Keep the catalog focus on " + _sanitize(product) + ".")
    if background_mode:
        prompt_parts.append(f"Follow {_sanitize(str(background_mode))} art direction" + (f" and preserve the focal area inside the {fold}% fold" if fold is not None else "") + ".")
    prompt_parts.append("Keep the composition mark-free, symbol-free, interface-free, people-free, product-accurate, and brand-safe while avoiding distorted merchandise or unsafe content.")

    refined = _single_paragraph(prompt_parts)
    if _word_count(refined) < 60:
        refined += " Keep lighting polished, depth natural, product edges crisp, and negative space uncluttered so the final banner remains accessible and conversion-focused."
    words = refined.split()
    while _word_count(" ".join(words)) > 120 and words:
        words.pop()
    if _word_count(refined) > 120:
        refined = " ".join(words[:120]).rstrip(" ,;:") + "."
    return refined
