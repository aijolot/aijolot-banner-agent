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
