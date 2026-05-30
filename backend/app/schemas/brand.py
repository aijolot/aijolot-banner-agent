"""BrandContext schema (GH-6).

Pydantic model that mirrors the ``brands/{id}.md`` frontmatter contract.
Used by the FastAPI bridge (GH-17) to validate reads and writes, and by the
ADK ``load_brand_context`` node downstream.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")


class PaletteColor(BaseModel):
    name: str = Field(..., min_length=1)
    hex: str

    @field_validator("hex")
    @classmethod
    def _valid_hex(cls, v: str) -> str:
        v = v.strip()
        if not _HEX_RE.match(v):
            raise ValueError(f"invalid hex color: {v!r} (expected #RRGGBB)")
        return v.upper()


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

    id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=1)
    palette: list[PaletteColor] = Field(..., min_length=1)
    typography: Typography = Field(default_factory=Typography)
    voice: Voice = Field(default_factory=Voice)
    logo_url: str | None = None
    image_style_directives: list[str] = Field(default_factory=list)
    shopify: Shopify
    # Free-form notes kept in the markdown body (not frontmatter).
    notes: str = ""


class BrandSummary(BaseModel):
    """Lightweight item for the ``GET /brands`` list view."""

    id: str
    name: str
    palette: list[PaletteColor]
