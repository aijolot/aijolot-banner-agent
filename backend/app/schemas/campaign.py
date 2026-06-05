"""Campaign schema (GH-27 / GH-28).

Mirrors the ``campaigns`` table: a free-text ``raw_brief`` plus a structured
``structured_brief`` (jsonb) holding the fields the intake agent extracts, and
a ``campaign_messages`` conversation log.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# Required fields for a "complete" brief (deadline is optional).
REQUIRED_BRIEF_FIELDS = ("goal", "audience", "cta", "urgency", "placement")


class PersonalizationVariant(BaseModel):
    """One customer variant the campaign personalizes for (served by tag).

    e.g. {key:"male", label:"Hombre", audience:"hombres 18-30", customer_tag:"gender:male"}.
    """

    key: str
    label: str = ""
    audience: str = ""
    customer_tag: str | None = None


class StructuredBrief(BaseModel):
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
