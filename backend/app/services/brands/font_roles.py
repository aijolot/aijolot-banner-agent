"""Brand-shape-tolerant font role resolution for generation surfaces (Task 8).

Mirrors ``color_roles.py``: every helper accepts a ``BrandContext`` model or a
plain dict and degrades to ``""``/``{}`` when typography is missing, so callers
(HTML renderer, Liquid payload builder, concept/image skills) keep their own
legacy defaults.

Resolution order per role (``display``/``headline``/``body``/``accent``/``caption``):

1. The typography role value, with role fallbacks: ``headline -> display``,
   ``accent -> headline -> display``, ``caption -> body``.
2. If that value matches an approved font family (case-insensitive,
   ``status="approved"``) the candidate's ``css_stack`` wins.
3. Else a comma in the value means it already is a stack and is used as-is.
4. Else a single family gets a generic fallback via ``build_css_stack``.

Every emitted stack passes :func:`quote_stack` (multi-word families double-quoted)
and a defensive character whitelist that mirrors the schema validation in
``app.schemas.brand`` — dict-shaped brands bypass Pydantic, so unsafe values are
treated as missing instead of reaching CSS/Liquid output.
"""

from __future__ import annotations

from typing import Any

from app.services.brands.color_roles import dump_model
from app.services.brands.font_discovery import build_css_stack, guess_font_category

_FONT_ROLES = ("display", "headline", "body", "accent")

_ROLE_FALLBACKS: dict[str, tuple[str, ...]] = {
    "display": ("display",),
    "headline": ("headline", "display"),
    "body": ("body",),
    "accent": ("accent", "headline", "display"),
    "caption": ("body",),
}

# Mirrors ``app.schemas.brand._FONT_STACK_EXTRA_CHARS`` (alnum + these chars only).
_STACK_EXTRA_CHARS = " -,'\""

# Aesthetic descriptors per font category for image prompts. Font NAMES never enter
# image prompts (generated imagery stays text/mark-free); only the vibe of the
# display category is allowed, phrased without any sanitizer-forbidden term.
_CATEGORY_AESTHETIC = {
    "sans": "geometric sans-serif aesthetic",
    "serif": "classic editorial serif aesthetic",
    "display": "bold poster-style display aesthetic",
    "mono": "precise technical monospace aesthetic",
    "handwritten": "organic handcrafted aesthetic",
}


def _sanitize_stack_value(value: Any) -> str:
    """Whitespace-collapse a font value; unsafe characters make it "" (missing)."""

    text = " ".join(str(value or "").split())
    if any(not (ch.isalnum() or ch in _STACK_EXTRA_CHARS) for ch in text):
        return ""
    return text


def quote_stack(stack: str) -> str:
    """Normalize a stack: multi-word families get double quotes, generics stay bare.

    Each comma-separated part is whitespace-collapsed; a part containing a space and
    no quote characters is wrapped in double quotes. Already-quoted parts (single or
    double) and single-word parts (incl. generics like ``sans-serif``) pass through.
    """

    parts: list[str] = []
    for raw in str(stack or "").split(","):
        part = " ".join(raw.split())
        if not part:
            continue
        if " " in part and '"' not in part and "'" not in part:
            part = f'"{part}"'
        parts.append(part)
    return ", ".join(parts)


def typography_data(brand: Any) -> dict[str, Any]:
    data = dump_model(brand)
    typography = data.get("typography") or getattr(brand, "typography", None)
    return dump_model(typography)


def _approved_fonts(brand: Any) -> list[dict[str, Any]]:
    """Approved-status candidates with safe family values (dict or model items)."""

    out: list[dict[str, Any]] = []
    for item in typography_data(brand).get("approved_fonts") or []:
        font = dump_model(item)
        family = _sanitize_stack_value(font.get("family"))
        # Entries inside approved_fonts default to approved when status is absent
        # (dict-shaped brands); an explicit candidate/discarded status is respected.
        status = str(font.get("status") or "approved").strip().lower()
        if not family or "," in family or status != "approved":
            continue
        out.append({**font, "family": family})
    return out


def _approved_match(brand: Any, family_string: str) -> dict[str, Any] | None:
    needle = family_string.strip().lower()
    if not needle:
        return None
    for font in _approved_fonts(brand):
        if font["family"].lower() == needle:
            return font
    return None


def _role_family_string(brand: Any, role: str) -> str:
    typography = typography_data(brand)
    for field in _ROLE_FALLBACKS.get(role, ()):
        value = _sanitize_stack_value(typography.get(field))
        if value:
            return value
    return ""


def _first_family(value: str) -> str:
    return value.split(",")[0].strip().strip("'\"").strip()


def resolve_font_stack(brand: Any, role: str) -> str:
    """CSS-safe font-family stack for a role, or "" when nothing resolves."""

    family_string = _role_family_string(brand, role)
    if not family_string:
        return ""
    match = _approved_match(brand, family_string)
    if match:
        stack = _sanitize_stack_value(match.get("css_stack"))
        if stack:
            return quote_stack(stack)
        # Approved entry with a broken/unsafe stack: rebuild from its family/category.
        category = str(match.get("category") or "") or guess_font_category(family_string)
        return quote_stack(build_css_stack(family_string, category))
    if "," in family_string:
        return quote_stack(family_string)
    return quote_stack(build_css_stack(family_string, guess_font_category(family_string)))


def resolve_font_family(brand: Any, role: str) -> str:
    """First family name a role resolves to (quotes stripped), or ""."""

    return _first_family(_role_family_string(brand, role))


def resolve_font_category(brand: Any, role: str) -> str:
    """Category for the role font: approved candidate category first, else a guess."""

    family_string = _role_family_string(brand, role)
    if not family_string:
        return ""
    match = _approved_match(brand, family_string)
    if match:
        category = str(match.get("category") or "").strip().lower()
        if category and category != "unknown":
            return category
    return guess_font_category(_first_family(family_string))


def font_aesthetic_hint(brand: Any, role: str = "display") -> str:
    """Short category-derived aesthetic phrase for image prompts, or "".

    Never contains font names and never contains image-sanitizer-forbidden terms.
    """

    return _CATEGORY_AESTHETIC.get(resolve_font_category(brand, role), "")


def font_prompt_lines(brand: Any) -> list[str]:
    """Concise per-role typography lines for text prompts.

    Only roles with a direct typography value are listed (inherited fallbacks would
    just repeat the display/body lines). Approved families are marked ``approved``
    with their category when known; everything else is marked ``legacy``.
    """

    typography = typography_data(brand)
    lines: list[str] = []
    for role in _FONT_ROLES:
        direct = _sanitize_stack_value(typography.get(role))
        if not direct:
            continue
        family = _first_family(direct)
        if not family:
            continue
        match = _approved_match(brand, direct)
        if match:
            category = str(match.get("category") or "").strip().lower()
            marker = f"approved, {category}" if category and category != "unknown" else "approved"
        else:
            marker = "legacy"
        lines.append(f"{role}: {family} ({marker})")
    return lines


def typography_config(brand: Any) -> dict[str, Any]:
    """JSON-safe typography block for the Liquid config.

    ``stacks`` carries resolved CSS stacks for roles with a direct typography value
    (empty resolutions omitted), ``approved_fonts`` is trimmed to
    family/category/recommended_roles, and ``legacy`` keeps the raw display/body
    strings for old readers. Returns ``{}`` when the brand has no typography at all.
    """

    typography = typography_data(brand)
    approved = _approved_fonts(brand)
    if not typography and not approved:
        return {}
    stacks: dict[str, str] = {}
    for role in _FONT_ROLES:
        if not _sanitize_stack_value(typography.get(role)):
            continue
        stack = resolve_font_stack(brand, role)
        if stack:
            stacks[role] = stack
    return {
        "stacks": stacks,
        "approved_fonts": [
            {
                "family": font["family"],
                "category": str(font.get("category") or "unknown"),
                "recommended_roles": [str(role) for role in (font.get("recommended_roles") or [])],
            }
            for font in approved
        ],
        "legacy": {
            "display": _sanitize_stack_value(typography.get("display")),
            "body": _sanitize_stack_value(typography.get("body")),
        },
    }


__all__ = [
    "font_aesthetic_hint",
    "font_prompt_lines",
    "quote_stack",
    "resolve_font_category",
    "resolve_font_family",
    "resolve_font_stack",
    "typography_config",
    "typography_data",
]
