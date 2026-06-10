from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

GenerationRunType = Literal["initial", "refinement", "v2_optimization"]
GenerationRunStatus = Literal["queued", "running", "succeeded", "failed", "escalated"]
GenerationEventStatus = Literal["started", "succeeded", "failed", "retried", "escalated"]
FrontendStep = Literal["intake_context", "concept", "image", "render_audit", "review_publish"]


class GenerationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_type: GenerationRunType = "initial"
    parent_run_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    started_by: str | None = Field(default=None, pattern=UUID_PATTERN)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FrontendProgressStep(BaseModel):
    key: FrontendStep
    label: str
    node_keys: list[str]
    status: GenerationRunStatus


class GenerationRunResponse(BaseModel):
    id: str
    campaign_id: str = Field(..., pattern=UUID_PATTERN)
    parent_run_id: str | None = None
    run_type: GenerationRunType
    status: GenerationRunStatus
    frontend_step: FrontendStep
    adk_trace_id: str | None = None
    started_by: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    progress: list[FrontendProgressStep] = Field(default_factory=list)


class GenerationEventResponse(BaseModel):
    id: str
    generation_run_id: str
    node_key: str
    frontend_step: FrontendStep
    status: GenerationEventStatus
    input_summary: dict[str, Any] | None = None
    output_summary: dict[str, Any] | None = None
    duration_ms: int | None = None
    cost_usd: float | None = None
    created_at: str | None = None

    @field_validator("input_summary", "output_summary", mode="before")
    @classmethod
    def _normalize_jsonb_summary(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        return {"value": value}


class RegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str | None = Field(default=None, min_length=1, max_length=8000)
    refinement_request_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    source_revision_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    requested_by: str | None = Field(default=None, pattern=UUID_PATTERN)
    # F9 — agentic refine: which nodes to re-run. Empty/None → inferred from the
    # prompt by the refinement-route classifier (default concept+copy).
    target_nodes: list[str] | None = Field(default=None)
    structured_changes: dict[str, Any] | None = Field(default=None)


class StructuredLayoutEdit(BaseModel):
    """Direct, instant layout edit (percent composition; camelCase to match the
    stored ``art_direction.layout`` shape). All optional — only present keys patch."""

    model_config = ConfigDict(extra="forbid")

    textX: float | None = None
    textY: float | None = None
    textW: float | None = None
    textAlign: str | None = None
    heroX: float | None = None
    heroY: float | None = None
    heroW: float | None = None
    heroH: float | None = None
    heroBehind: bool | None = None


class StructuredFontsEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display: str | None = None
    body: str | None = None


class StructuredCopyEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str | None = None
    subheadline: str | None = None
    eyebrow: str | None = None
    cta: str | None = None


class StructuredEdit(BaseModel):
    """A direct, no-LLM banner edit. Every section is optional and server-clamped
    (layout via clamp_layout, fonts via the allow-list, runs via contrast gating)."""

    model_config = ConfigDict(extra="forbid")

    layout: StructuredLayoutEdit | None = None
    fonts: StructuredFontsEdit | None = None
    # Global text color (hex string) — or a per-section dict keyed by
    # headline|subheadline|eyebrow|cta (W0.3).
    ink: str | dict[str, str] | None = None
    # Per-section font-size multiplier (0.5–2.5 = 50%–250%), keyed by
    # headline|subheadline|eyebrow|cta (W0.3). Values are server-clamped.
    type_scale: dict[str, float] | None = None
    copy: StructuredCopyEdit | None = None
    # Per-variant headline emphasis runs, keyed by banner_variant_id.
    headline_runs: dict[str, list[dict[str, Any]]] | None = None


class ApplyEditsRequest(BaseModel):
    """Request for POST /campaigns/{id}/apply-edits (instant edit, no agent run)."""

    model_config = ConfigDict(extra="forbid")

    structured_changes: StructuredEdit
    source_revision_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    requested_by: str | None = Field(default=None, pattern=UUID_PATTERN)


class RevisionVariantResponse(BaseModel):
    id: str
    revision_id: str = Field(..., pattern=UUID_PATTERN)
    segment_key: str
    segment_label: str
    customer_tag: str | None = None
    audience_rule: dict[str, Any] = Field(default_factory=dict)
    product_snapshot_item_id: str | None = None
    eyebrow: str | None = None
    headline: str | None = None
    subheadline: str | None = None
    cta_text: str | None = None
    cta_url: str | None = None
    palette: dict[str, Any] = Field(default_factory=dict)


class LayoutVariantResponse(BaseModel):
    id: str
    revision_id: str = Field(..., pattern=UUID_PATTERN)
    key: str
    name: str
    description: str | None = None
    layout_type: str | None = None
    is_recommended: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class CampaignRevisionResponse(BaseModel):
    id: str
    campaign_id: str = Field(..., pattern=UUID_PATTERN)
    generation_run_id: str | None = None
    revision_number: int
    status: str
    concept: dict[str, Any] = Field(default_factory=dict)
    liquid_config: dict[str, Any] = Field(default_factory=dict)
    html_preview: str | None = None
    preview_storage_path: str | None = None
    created_at: str | None = None
    layout_variants: list[LayoutVariantResponse] = Field(default_factory=list)
    variants: list[RevisionVariantResponse] = Field(default_factory=list)


class RegenerateResponse(BaseModel):
    generation_run: GenerationRunResponse
    revision: CampaignRevisionResponse
    refinement_request_id: str | None = None


class CampaignPlanResponse(BaseModel):
    """Cheap, human-readable plan surfaced BEFORE the costly build phase.

    Built deterministically from the concept + art direction + background, plus a
    wireframe spec (the ``bannerLiveHTML`` ``live`` shape with ``imageUrl=""`` so
    the frontend renders boxes/colors with no generated image).
    """

    revision_id: str
    campaign_id: str = Field(..., pattern=UUID_PATTERN)
    generation_run_id: str | None = None
    status: str = "plan"
    theme: str = ""
    typography: dict[str, Any] = Field(default_factory=dict)
    color_guidance: dict[str, Any] = Field(default_factory=dict)
    product_intent: list[dict[str, Any]] = Field(default_factory=list)
    copy_preview: dict[str, Any] = Field(default_factory=dict)
    layout_note: str = ""
    hierarchy_notes: str = ""
    wireframe: dict[str, Any] = Field(default_factory=dict)
    decision_trace: dict[str, Any] = Field(default_factory=dict)
    estimated_image_cost_note: str = ""


class VariantSelectionResponse(BaseModel):
    campaign_id: str = Field(..., pattern=UUID_PATTERN)
    selected_revision_id: str = Field(..., pattern=UUID_PATTERN)
    selected_variant_id: str
    campaign_status: str
    revision: CampaignRevisionResponse
