"""BrandContext schema (GH-6).

Pydantic model that mirrors the ``brands/{id}.md`` frontmatter contract.
Used by the FastAPI bridge (GH-17) to validate reads and writes, and by the
ADK ``load_brand_context`` node downstream.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")

ROLE_DEFAULTS = {
    "primary": {
        "label": "Primary",
        "usage_hint": "Main brand color for dominant identity moments, headline emphasis, and major visual anchors.",
        "agent_hint": "Prefer for main brand identity, key text/visual anchors, and high-recognition surfaces.",
    },
    "secondary": {
        "label": "Secondary",
        "usage_hint": "Support color for backgrounds, secondary surfaces, and balance around the primary color.",
        "agent_hint": "Use for background fields, supporting surfaces, and composition balance.",
    },
    "tertiary": {
        "label": "Tertiary / Accent",
        "usage_hint": "Accent color for CTA, highlights, badges, and small high-attention elements.",
        "agent_hint": "Use sparingly for CTA, promotional badges, urgency marks, and highlights.",
    },
}


def _normalize_hex(v: str) -> str:
    v = v.strip()
    if not _HEX_RE.match(v):
        raise ValueError(f"invalid hex color: {v!r} (expected #RRGGBB)")
    return v.upper()


class PaletteColor(BaseModel):
    name: str = Field(..., min_length=1)
    hex: str

    @field_validator("hex")
    @classmethod
    def _valid_hex(cls, v: str) -> str:
        return _normalize_hex(v)


class BrandColorVariant(BaseModel):
    name: str = Field(..., min_length=1)
    hex: str
    usage_hint: str = ""
    source: str = "manual"

    @field_validator("hex")
    @classmethod
    def _valid_hex(cls, v: str) -> str:
        return _normalize_hex(v)


class BrandColorRole(BaseModel):
    key: str = Field(..., pattern=r"^(primary|secondary|tertiary)$")
    label: str = Field(..., min_length=1)
    hex: str
    usage_hint: str = ""
    agent_hint: str = ""
    variants: list[BrandColorVariant] = Field(default_factory=list)

    @field_validator("hex")
    @classmethod
    def _valid_hex(cls, v: str) -> str:
        return _normalize_hex(v)


class BrandColorSystem(BaseModel):
    primary: BrandColorRole
    secondary: BrandColorRole
    tertiary: BrandColorRole

    @model_validator(mode="after")
    def _role_keys_match_fields(self) -> "BrandColorSystem":
        for expected_key in ("primary", "secondary", "tertiary"):
            role = getattr(self, expected_key)
            if role.key != expected_key:
                raise ValueError(f"{expected_key} role must use key={expected_key!r}")
        return self


def _role_from_palette(key: str, palette_color: PaletteColor) -> BrandColorRole:
    defaults = ROLE_DEFAULTS[key]
    return BrandColorRole(
        key=key,
        label=defaults["label"],
        hex=palette_color.hex,
        usage_hint=defaults["usage_hint"],
        agent_hint=defaults["agent_hint"],
    )


def color_system_from_palette(palette: list[PaletteColor]) -> BrandColorSystem:
    primary = palette[0]
    secondary = palette[1] if len(palette) > 1 else primary
    tertiary = palette[2] if len(palette) > 2 else secondary
    return BrandColorSystem(
        primary=_role_from_palette("primary", primary),
        secondary=_role_from_palette("secondary", secondary),
        tertiary=_role_from_palette("tertiary", tertiary),
    )


# Font values end up inside CSS (font-family declarations) and Liquid settings, so
# they are whitelist-validated instead of trusting arbitrary strings. The whitelists
# below provably reject the dangerous inputs (< > { } ; ( ) & \ / ` @ control chars,
# and therefore also url(, expression(, @import) because none of those characters are
# allowed at all.
_FONT_FAMILY_EXTRA_CHARS = " -"
_FONT_STACK_EXTRA_CHARS = " -,'\""

FontRoleKey = Literal["display", "headline", "body", "accent", "caption"]
FontCategory = Literal["sans", "serif", "display", "mono", "handwritten", "unknown"]
FontSource = Literal["shopify_theme", "storefront_css", "gemini_suggested", "system_seed", "manual"]
FontStatus = Literal["candidate", "approved", "discarded"]


def _normalize_font_value(v: str, *, extra_chars: str, kind: str) -> str:
    # str.split() collapses/strips all unicode whitespace (incl. tabs/newlines).
    v = " ".join(v.split())
    bad = sorted({ch for ch in v if not (ch.isalnum() or ch in extra_chars)})
    if bad:
        raise ValueError(f"{kind} contains unsupported characters: {bad!r}")
    return v


def _normalize_font_family(v: str) -> str:
    """Normalize a single font family name: letters/digits/spaces/hyphens only."""

    v = _normalize_font_value(v, extra_chars=_FONT_FAMILY_EXTRA_CHARS, kind="font family")
    if not v:
        raise ValueError("font family must not be empty")
    return v


def _normalize_font_stack(v: str) -> str:
    """Normalize a CSS font-family stack: family characters plus commas/quotes."""

    return _normalize_font_value(v, extra_chars=_FONT_STACK_EXTRA_CHARS, kind="font stack")


class FontCandidate(BaseModel):
    """A discovered/suggested font family moving through candidate -> approved/discarded."""

    family: str
    css_stack: str
    category: FontCategory = "unknown"
    source: FontSource
    status: FontStatus = "candidate"
    recommended_roles: list[FontRoleKey] = Field(default_factory=list)
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("family")
    @classmethod
    def _safe_family(cls, v: str) -> str:
        return _normalize_font_family(v)

    @field_validator("css_stack")
    @classmethod
    def _safe_css_stack(cls, v: str) -> str:
        v = _normalize_font_stack(v)
        if not v:
            raise ValueError("css_stack must not be empty")
        return v


class Typography(BaseModel):
    # Legacy fields: every existing payload only carries these two.
    display: str = "Space Grotesk"
    body: str = "Inter"
    # Optional role assignments and the approved/discarded font system (discovery flow).
    headline: str | None = None
    accent: str | None = None
    approved_fonts: list[FontCandidate] = Field(default_factory=list)
    discarded_fonts: list[FontCandidate] = Field(default_factory=list)

    @field_validator("display", "body", "headline", "accent")
    @classmethod
    def _safe_font_value(cls, v: str | None) -> str | None:
        if v is None:
            return None
        # Stack rule (commas/quotes allowed) keeps any historically stored value such
        # as "Helvetica Neue, sans-serif" valid while still blocking CSS injection.
        # Empty strings stay allowed for backward compatibility.
        return _normalize_font_stack(v)


class Voice(BaseModel):
    tone: list[str] = Field(default_factory=list)
    prohibited_words: list[str] = Field(default_factory=list)
    required_phrases: list[str] = Field(default_factory=list)


class Shopify(BaseModel):
    store_domain: str
    theme_id: str | None = None
    default_placement: str = "hero"


class BrandContext(BaseModel):
    """Full brand context persisted per store."""

    id: str = Field(..., pattern=r"^[a-z0-9_-]+$")
    name: str = Field(..., min_length=1)
    palette: list[PaletteColor] = Field(..., min_length=1)
    color_system: BrandColorSystem | None = None
    typography: Typography = Field(default_factory=Typography)
    voice: Voice = Field(default_factory=Voice)
    logo_url: str | None = None
    image_style_directives: list[str] = Field(default_factory=list)
    shopify: Shopify
    # Free-form notes kept in the markdown body (not frontmatter).
    notes: str = ""

    @model_validator(mode="after")
    def _ensure_color_system(self) -> "BrandContext":
        if self.color_system is None:
            self.color_system = color_system_from_palette(self.palette)
        return self


def ensure_color_system(brand: BrandContext) -> BrandContext:
    """Return a brand with color_system populated from legacy palette if needed."""

    if brand.color_system is not None:
        return brand
    return brand.model_copy(update={"color_system": color_system_from_palette(brand.palette)})


class BrandSummary(BaseModel):
    """Lightweight item for the ``GET /brands`` list view."""

    id: str
    name: str
    palette: list[PaletteColor]
