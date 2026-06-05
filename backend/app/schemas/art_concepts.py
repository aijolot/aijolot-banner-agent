"""Schemas for the Art Direction per-variant concept proposal (art-direction skill)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ShotType = Literal["hero", "usage"]


class ConceptProductRef(BaseModel):
    title: str = ""
    sku: str | None = None
    price: float | None = None
    image_url: str | None = None


class ArtConceptVariant(BaseModel):
    """One proposed art concept for a personalization variant."""

    variant_key: str
    label: str = ""
    customer_tag: str | None = None
    audience: str = ""
    shot_type: ShotType = "hero"
    layout: str = ""
    layout_source: str | None = None  # KG doc title
    copy: dict[str, str] = Field(default_factory=dict)  # eyebrow/headline/subheadline/cta
    background: dict[str, str] = Field(default_factory=dict)  # name/description/css
    product: ConceptProductRef | None = None
    product_rationale: str = ""
    model_treatment: str | None = None  # usage only
    rationale: str = ""
    origin_tags: dict[str, str] = Field(default_factory=dict)


class ArtConceptsRequest(BaseModel):
    revision_id: str | None = None
    feedback: str | None = None  # iteration note from the designer
    focus_variant: str | None = None  # variant_key to re-focus on feedback
    focus: str | None = None  # copy | background | product | model | layout


class ArtConceptsResponse(BaseModel):
    campaign_id: str
    revision_id: str | None = None
    personalization_dimension: str = ""
    source: str = "deterministic"  # "gemini" | "deterministic"
    concepts: list[ArtConceptVariant] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
