"""Campaign schema (GH-27 / GH-28).

Mirrors the ``campaigns`` table: a free-text ``raw_brief`` plus a structured
``structured_brief`` (jsonb) holding the fields the intake agent extracts, and
a ``campaign_messages`` conversation log.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# Required fields for a "complete" brief (deadline is optional).
REQUIRED_BRIEF_FIELDS = ("goal", "audience", "cta", "urgency", "placement")

# A destination is either an absolute http(s) URL or a site-relative path
# (e.g. "/collections/all"), matching the storefront convention.
_DESTINATION_URL_RE = re.compile(r"^(https?://\S+|/\S*)$")


class BriefProduct(BaseModel):
    """A product selected at the campaign level (mirrors the per-variant product
    fields so the frontend payload maps 1:1)."""

    product_gid: str | None = None
    product_title: str = ""
    product_image_url: str | None = None
    price: str | None = None


class PersonalizationVariant(BaseModel):
    """One customer variant the campaign personalizes for (served by tag).

    e.g. {key:"male", label:"Hombre", audience:"hombres 18-30", customer_tag:"gender:male"}.
    """

    key: str
    label: str = ""
    audience: str = ""
    customer_tag: str | None = None
    # Optional featured product for THIS variant (resolved from the Shopify catalog,
    # e.g. via /stores/{id}/shopify/products/search). When set, the variant's copy is
    # grounded on this product instead of the shared catalog snapshot — so e.g. the men
    # variant features "Mandarin Sky" and the women variant "My Way Intense".
    product_gid: str | None = None
    product_title: str | None = None
    product_image_url: str | None = None


class StructuredBrief(BaseModel):
    # Idioma de TODO lo que el cliente ve de esta campaña (copy, rationales,
    # trazas, chat) — lo fija el switcher del UI vía X-Aijolot-Lang.
    language: str = "es"
    goal: str = ""
    audience: str = ""
    cta: str = ""
    tone: str = ""
    urgency: str = ""  # low | medium | high
    placement: str = ""
    deadline: str | None = None  # ISO date (YYYY-MM-DD) or None
    promo: str = ""  # parsed offer/discount label, e.g. "15% OFF" (→ campaign.promo_label)
    # Optional personalization dimension: one banner_variant is generated per
    # entry (1 campaign, N variants served by customer tag). Empty → single default.
    personalization_dimension: str = ""  # e.g. "gender"
    personalization_variants: list[PersonalizationVariant] = Field(default_factory=list)
    # Optional campaign-level products to feature (in addition to per-variant ones)
    # and the destination the banner CTA links to (absolute URL or "/path").
    products: list[BriefProduct] = Field(default_factory=list)
    destination_url: str | None = None

    @field_validator("destination_url", mode="before")
    @classmethod
    def _validate_destination_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if not _DESTINATION_URL_RE.match(text):
            raise ValueError("destination_url must be an http(s) URL or a site-relative path (e.g. /collections/all)")
        return text

    def missing(self) -> list[str]:
        return [f for f in REQUIRED_BRIEF_FIELDS if not getattr(self, f).strip()]

    def is_complete(self) -> bool:
        return not self.missing()


class CampaignMessage(BaseModel):
    author_type: Literal["user", "agent", "system"]
    body: str
    metadata: dict = Field(default_factory=dict)


class Campaign(BaseModel):
    id: str
    title: str = ""
    raw_brief: str = ""
    structured_brief: StructuredBrief = Field(default_factory=StructuredBrief)
    status: str = "draft"
    messages: list[CampaignMessage] = Field(default_factory=list)


class IntakeRequest(BaseModel):
    message: str
    campaign_id: str | None = None
    # Idioma del switcher del UI: fija structured_brief.language ANTES de
    # extraer y responder, para que el chat nunca mezcle idiomas.
    language: str | None = None


class BriefPatch(BaseModel):
    """Partial update for the structured brief (GH-28 PATCH)."""

    goal: str | None = None
    audience: str | None = None
    cta: str | None = None
    tone: str | None = None
    urgency: str | None = None
    placement: str | None = None
    deadline: str | None = None
    title: str | None = None
    promo: str | None = None
    personalization_dimension: str | None = None
    personalization_variants: list[dict[str, Any]] | None = None
    products: list[dict[str, Any]] | None = None
    destination_url: str | None = None

    @field_validator("destination_url", mode="before")
    @classmethod
    def _validate_patch_destination_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if not _DESTINATION_URL_RE.match(text):
            raise ValueError("destination_url must be an http(s) URL or a site-relative path (e.g. /collections/all)")
        return text
