"""BrandContext schema (GH-6).

Pydantic model that mirrors the ``brands/{id}.md`` frontmatter contract.
Used by the FastAPI bridge (GH-17) to validate reads and writes, and by the
ADK ``load_brand_context`` node downstream.
"""

from __future__ import annotations

import re

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


class Typography(BaseModel):
    display: str = "Space Grotesk"
    body: str = "Inter"


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
