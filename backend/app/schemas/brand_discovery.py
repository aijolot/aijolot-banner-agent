"""Brand discovery data contracts.

Shopify-derived raw evidence (``BrandDiscoverySnapshot``) is stored separately from
approved brand settings, and Gemini-backed recommendation drafts
(``BrandRecommendationDraft``) stay drafts until the user explicitly applies them
onto ``BrandContext.color_system`` / ``BrandContext.typography``.

Schema-only module: keep it import-light (no service imports).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.brand import (
    BrandColorVariant,
    FontCandidate,
    _normalize_font_family,
    _normalize_font_stack,
    _normalize_hex,
)

BrandDiscoveryStatus = Literal["pending", "running", "succeeded", "failed", "partial"]
BrandColorRoleKey = Literal["primary", "secondary", "tertiary"]


class BrandDiscoveryAsset(BaseModel):
    """A single piece of raw evidence (logo, theme asset, css file, ...)."""

    kind: Literal["logo", "banner", "hero", "theme_asset", "css", "settings", "unknown"]
    url: str | None = None
    shopify_gid: str | None = None
    theme_asset_key: str | None = None
    content_type: str | None = None
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscoveredColor(BaseModel):
    """A color extracted from Shopify evidence, with provenance and confidence."""

    hex: str
    name: str = ""
    source: str
    confidence: float = Field(default=0.0, ge=0, le=1)
    usage_hint: str = ""

    @field_validator("hex")
    @classmethod
    def _valid_hex(cls, value: str) -> str:
        return _normalize_hex(value)


class DiscoveredFont(BaseModel):
    """A font family extracted from Shopify evidence, with provenance and confidence."""

    family: str
    source: str
    css_stack: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    sample_usage: str = ""

    @field_validator("family")
    @classmethod
    def _safe_family(cls, value: str) -> str:
        return _normalize_font_family(value)

    @field_validator("css_stack")
    @classmethod
    def _safe_css_stack(cls, value: str) -> str:
        # Optional for raw evidence (extractors may only know the family name).
        return _normalize_font_stack(value)


class BrandDiscoverySnapshot(BaseModel):
    """Raw discovered evidence for one discovery run, before user approval."""

    id: str
    brand_id: str
    store_id: str | None = None
    shop_domain: str
    status: BrandDiscoveryStatus
    discovered_at: datetime
    source_summary: str = ""
    assets: list[BrandDiscoveryAsset] = Field(default_factory=list)
    colors: list[DiscoveredColor] = Field(default_factory=list)
    fonts: list[DiscoveredFont] = Field(default_factory=list)
    theme_metadata: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class BrandColorRecommendation(BaseModel):
    """A recommended color role draft generated from discovery evidence."""

    role_key: BrandColorRoleKey
    base_hex: str
    label: str = Field(..., min_length=1)
    usage_hint: str
    agent_hint: str
    variants: list[BrandColorVariant] = Field(default_factory=list)
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("base_hex")
    @classmethod
    def _valid_base_hex(cls, value: str) -> str:
        return _normalize_hex(value)


class BrandRecommendationDraft(BaseModel):
    """Draft recommendations awaiting explicit user acceptance.

    Nothing in this draft becomes active until accepted items are applied onto the
    ``BrandContext`` (colors into ``color_system`` roles, fonts into typography).
    """

    colors: list[BrandColorRecommendation] = Field(default_factory=list)
    fonts: list[FontCandidate] = Field(default_factory=list)
    summary: str = ""
    source_notes: list[str] = Field(default_factory=list)
