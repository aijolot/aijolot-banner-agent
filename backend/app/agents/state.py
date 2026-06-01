"""ADK session state passed across the 12 graph nodes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.brand import BrandContext


class Campaign(BaseModel):
    goal: str
    audience: str
    cta: str
    tone: str
    urgency: str
    placement: str
    deadline: datetime | None = None


class Variant(BaseModel):
    customer_tag: str
    intent_delta: str
    copy_override: dict[str, str] | None = None


class Concept(BaseModel):
    layout: str
    copy: dict[str, str]
    palette_usage: dict[str, str]
    image_prompt: str
    hierarchy_notes: str


class BannerAssets(BaseModel):
    webp: dict[int, str]
    avif: dict[int, str]
    fallback_jpg: dict[int, str]
    alt_text_suggestion: str
    total_weight_kb_1280_webp: float
    asset_records: list[dict[str, Any]] = Field(default_factory=list)
    optimization_report: dict[str, Any] = Field(default_factory=dict)


class AuditReport(BaseModel):
    html_w3c: str
    lighthouse: dict[str, float]
    schema_valid: bool
    breakpoints_render: dict[str, bool]
    root_cause_hint: str | None = None
    overall_pass: bool


class HITLDecision(BaseModel):
    action: str  # approve | reject | edit_request | schedule
    target_publish_at: datetime | None = None
    reviewer: str
    notes: str | None = None


class PublishResult(BaseModel):
    shopify_section_id: str
    theme_id: str
    asset_urls: list[str]


class BannerSessionState(BaseModel):
    """In-graph state. Passed by reference between nodes via ADK."""

    trace_id: str
    session_id: str
    brand_id: str

    brand_context: BrandContext | None = None
    campaign: Campaign | None = None
    variants: list[Variant] = Field(default_factory=list)
    best_practices: list[dict[str, Any]] = Field(default_factory=list)
    concept: Concept | None = None
    image_bytes: bytes | None = None
    assets: BannerAssets | None = None
    html_standalone: str | None = None
    liquid_section: str | None = None
    audit_report: AuditReport | None = None
    hitl_decision: HITLDecision | None = None
    scheduled_at: datetime | None = None
    publish_result: PublishResult | None = None

    cost_usd_running: float = 0.0
    retries: dict[str, int] = Field(default_factory=dict)  # node -> count, max 2

    class Config:
        arbitrary_types_allowed = True
