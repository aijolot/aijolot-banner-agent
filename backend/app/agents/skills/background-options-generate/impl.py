"""background-options-generate skill (F7).

Generate self-contained HTML/CSS background treatments for the `.aijolot-banner`
surface. Gemini FLASH (structured) when available + within cost cap; otherwise
deterministic brand-palette gradients. All CSS/HTML is sanitized before return.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.tools import gemini_text
from app.core.settings import Settings
from app.schemas.backgrounds import BackgroundOption, BackgroundOptionsOutput

EST_BACKGROUND_USD = 0.002

# Patterns that must never reach a rendered preview.
_CSS_FORBIDDEN = (
    re.compile(r"@import[^;]*;?", re.IGNORECASE),
    re.compile(r"url\(\s*['\"]?\s*(?:https?:)?//[^)]*\)", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"-moz-binding[^;]*;?", re.IGNORECASE),
    re.compile(r"behavior\s*:[^;]*;?", re.IGNORECASE),
    re.compile(r"</?\s*style[^>]*>", re.IGNORECASE),
)
_HTML_FORBIDDEN = (
    re.compile(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.S),
    re.compile(r"<\s*script\b[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*iframe\b[^>]*>.*?<\s*/\s*iframe\s*>", re.IGNORECASE | re.S),
    re.compile(r"<\s*iframe\b[^>]*>", re.IGNORECASE),
    # SVG <foreignObject> can smuggle arbitrary HTML/script into an inline svg.
    re.compile(r"<\s*foreignObject\b[^>]*>.*?<\s*/\s*foreignObject\s*>", re.IGNORECASE | re.S),
    re.compile(r"<\s*foreignObject\b[^>]*>", re.IGNORECASE),
    re.compile(r"\son\w+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE),
    # javascript: in any href/xlink:href (SVG <a>/<use>) or inline.
    re.compile(r"javascript\s*:", re.IGNORECASE),
)


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def sanitize_css(css: str) -> str:
    cleaned = str(css or "")
    for pattern in _CSS_FORBIDDEN:
        cleaned = pattern.sub("", cleaned)
    return " ".join(cleaned.split()).strip()


def sanitize_html(html: str) -> str:
    cleaned = str(html or "")
    for pattern in _HTML_FORBIDDEN:
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip()


def _is_valid_css(css: str) -> bool:
    # Must contain at least one declaration and look like background styling.
    return bool(css) and ":" in css and "background" in css.lower()


def _palette(brand_context: Any) -> list[tuple[str, str]]:
    palette = _get(brand_context, "palette", []) or []
    out: list[tuple[str, str]] = []
    for color in palette:
        name = str(_get(color, "name", "") or "Color")
        hex_value = str(_get(color, "hex", "") or "")
        if hex_value:
            out.append((name, hex_value))
    if not out:
        out = [("Ink", "#111111"), ("Canvas", "#FFFFFF")]
    return out


def _fallback_options(brand_context: Any, count: int) -> list[BackgroundOption]:
    palette = _palette(brand_context)
    primary = palette[0][1]
    secondary = palette[1][1] if len(palette) > 1 else "#FFFFFF"
    accent = palette[2][1] if len(palette) > 2 else primary
    recipes = [
        (
            "Linear brand gradient",
            "Diagonal gradient from primary to secondary palette tones",
            f".aijolot-banner{{background:linear-gradient(135deg,{primary} 0%,{secondary} 100%);color:#ffffff;}}",
        ),
        (
            "Radial spotlight",
            "Soft radial glow centered behind the hero copy",
            f".aijolot-banner{{background:radial-gradient(circle at 30% 50%,{accent} 0%,{primary} 70%);color:#ffffff;}}",
        ),
        (
            "Duotone band",
            "Solid primary field with an accent base band for depth",
            f".aijolot-banner{{background:linear-gradient(180deg,{primary} 0%,{primary} 70%,{accent} 100%);color:#ffffff;}}",
        ),
        (
            "Soft canvas wash",
            "Light secondary wash for dark-on-light copy",
            f".aijolot-banner{{background:linear-gradient(160deg,{secondary} 0%,#ffffff 100%);color:{primary};}}",
        ),
        (
            "Accent corner sweep",
            "Primary field with an accent corner sweep",
            f".aijolot-banner{{background:linear-gradient(45deg,{primary} 60%,{accent} 100%);color:#ffffff;}}",
        ),
    ]
    options: list[BackgroundOption] = []
    for name, description, css in recipes[: max(1, count)]:
        options.append(
            BackgroundOption(
                name=name,
                description=description,
                css=sanitize_css(css),
                html='<section class="aijolot-banner"></section>',
                rationale="Derived from brand palette tokens with light/dark contrast.",
            )
        )
    return options


def _directed_edit_block(instruction: str, base_background: Any) -> str:
    """Prompt block for a DIRECTED edit of an existing background (W0.1).

    Used when the user asked for a specific tweak (e.g. swap a decorative SVG
    motif) — the model must modify the current treatment, not invent a new one.
    """
    if not instruction:
        return ""
    base_css = sanitize_css(str(_get(base_background, "css", "") or ""))
    base_html = sanitize_html(str(_get(base_background, "html", "") or ""))
    block = (
        "\nDIRECTED EDIT MODE: the user is iterating on an EXISTING background. Do NOT invent a new look.\n"
        f'Apply exactly this request to the current treatment: "{instruction}".\n'
        "Keep the current colors, gradient, mood and composition UNCHANGED except for what the request asks "
        "(e.g. if the request swaps a decorative SVG shape, only the shape changes — same palette, same layout "
        "of the motif, same density). Return the edited treatment as option 1.\n"
    )
    if base_css:
        block += f"Current CSS:\n{base_css}\n"
    if base_html:
        block += f"Current HTML wrapper:\n{base_html}\n"
    return block


def _build_prompt(concept: Any, brand_context: Any, count: int, *, instruction: str = "", base_background: Any = None, lang_label: str = "Spanish (Mexico)") -> str:
    copy = _get(concept, "copy", {}) or {}
    headline = _get(copy, "headline", "") if isinstance(copy, dict) else ""
    subheadline = _get(copy, "subheadline", "") if isinstance(copy, dict) else ""
    layout = _get(concept, "layout", "")
    image_prompt = _get(concept, "image_prompt", "")
    palette_lines = ", ".join(f"{name} {hex_value}" for name, hex_value in _palette(brand_context))
    tone = " ".join(_get(_get(brand_context, "voice", None), "tone", []) or [])
    return (
        f"You are a senior ecommerce art director. Propose exactly {count} DISTINCT background "
        "treatments for a Shopify banner hero surface.\n"
        + _directed_edit_block(instruction, base_background)
        + "\n"
        f"Campaign theme / headline: {headline}\nSupporting line: {subheadline}\n"
        f"Scene/mood context: {image_prompt}\nLayout: {layout}\nBrand tone: {tone}\n"
        f"Brand palette: {palette_lines}\n\n"
        "The backgrounds MUST evoke the campaign's theme, season, and product mood from the context above. "
        "Match the MOOD over the brand neutrals: e.g. summer/cítrico/frutal → vibrant, playful, sun-drenched — "
        "saturated sky blues, corals, sunny yellows, hot pinks, teals, tropical sunset gradients (think a fun "
        "summer-vibes banner, NOT a dark corporate 'premium' look). Use the brand palette only as accents; you "
        "MAY introduce theme-appropriate hues beyond it when the campaign theme calls for it. "
        "Make the options visually distinct and high-energy, not subtle.\n"
        "Go BEYOND plain gradients: across the options, propose genuinely different treatments — at least one "
        "should use a PATTERN (e.g. an inline data-URI SVG `background-image` of repeating shapes, diagonal/curved "
        "LINES, dots/halftone, organic blobs, confetti, sunbursts, or a geometric motif) layered over a color base, "
        "so they feel art-directed, not just color washes.\n"
        "Requirements for EACH option:\n"
        "- CSS MUST be a single rule scoped to `.aijolot-banner` (you may add nested selectors under it).\n"
        "- You MAY use `background-image: url(\"data:image/svg+xml,...\")` with an inline SVG pattern (URL-encode it), "
        "and/or layered gradients (linear + radial + conic). You MAY also put a decorative inline `<svg>` in the html "
        "wrapper as a backdrop layer. NO external assets, NO url() to the web (http/https), NO @import, NO <script>, "
        "NO event handlers, NO raster images.\n"
        "- The whole surface must stay BRIGHT and saturated edge to edge. Do NOT cover the copy area with a dark "
        "scrim/overlay (no near-black `rgba(0,0,0,..)` or `rgba(17,17,17,..)` layers, no dark vignette). If the copy "
        "needs contrast, keep the background light and set a DARK text `color`, or add a subtle WHITE/light glass "
        "panel behind the text — never darken the whole banner.\n"
        "- Ensure accessible contrast for overlaid HTML copy by choosing a legible `color` against the BRIGHT "
        "background (dark ink on light/warm fields), not by dimming the art.\n"
        "- Provide a short name, a one-line description, the css, a minimal html wrapper, and a rationale.\n"
        f"Name, description and rationale MUST be written in {lang_label}.\n"
        "Return JSON matching the provided schema."
    )


async def run(
    concept: Any,
    brand_context: Any,
    *,
    count: int = 3,
    cost_guard: Any = None,
    settings: Any = None,
    instruction: str = "",
    base_background: Any = None,
    lang: str = "es",
) -> tuple[list[BackgroundOption], str]:
    """Return (options, source) where source is 'gemini' or 'deterministic'.

    ``instruction`` + ``base_background`` switch the skill into directed-edit
    mode (W0.1): the model modifies the existing treatment instead of inventing
    a new one. The deterministic fallback cannot honor directed edits — callers
    that need decor-only changes should keep the previous background when this
    returns source='deterministic'.
    """

    count = max(1, min(int(count or 3), 5))

    resolved_settings = settings or Settings.from_env()
    if not resolved_settings.has_google_api_key():
        return _fallback_options(brand_context, count), "deterministic"

    from app.services.gemini.cost_guard import get_default_cost_guard

    guard = cost_guard or get_default_cost_guard(resolved_settings)
    reservation = guard.check_and_reserve(EST_BACKGROUND_USD)
    if not reservation.allowed:
        return _fallback_options(brand_context, count), "deterministic"

    try:
        from app.core.i18n import lang_name

        result = await gemini_text.generate(
            _build_prompt(concept, brand_context, count, instruction=instruction, base_background=base_background, lang_label=lang_name(lang)),
            model=gemini_text.FLASH_MODEL,
            structured=BackgroundOptionsOutput,
        )
    except gemini_text.GeminiUnavailable:
        return _fallback_options(brand_context, count), "deterministic"

    raw_options = list(getattr(result, "options", []) or [])
    if not raw_options:
        return _fallback_options(brand_context, count), "deterministic"

    fallback = _fallback_options(brand_context, count)
    sanitized: list[BackgroundOption] = []
    for index, option in enumerate(raw_options[:count]):
        css = sanitize_css(_get(option, "css", ""))
        html = sanitize_html(_get(option, "html", "")) or '<section class="aijolot-banner"></section>'
        if not _is_valid_css(css):
            # Emptied/invalid after sanitization → substitute a safe gradient.
            sanitized.append(fallback[index % len(fallback)])
            continue
        sanitized.append(
            BackgroundOption(
                name=str(_get(option, "name", f"Option {index + 1}")) or f"Option {index + 1}",
                description=str(_get(option, "description", "")),
                css=css,
                html=html,
                rationale=str(_get(option, "rationale", "")),
            )
        )
    if not sanitized:
        return fallback, "deterministic"
    return sanitized, "gemini"
