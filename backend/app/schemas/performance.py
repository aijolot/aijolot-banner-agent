from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
PerformanceSource = Literal["manual", "mock", "seed", "agent", "shopify", "analytics", "lighthouse"]
ProposalStatus = Literal["draft", "sent_to_approval", "accepted", "rejected"]
NON_LIVE_LABEL = "Manual/mock metrics — not live analytics"
NON_LIVE_NOTE = "Performance data is manually entered, mock, seed, or agent-proposed; not live analytics."
LIVE_SOURCE_LABEL = "Imported analytics metrics — source-labeled as live data"
LIVE_SOURCES = {"shopify", "analytics", "lighthouse"}


class PerformanceSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    source: PerformanceSource = "manual"
    window_start: str | None = None
    window_end: str | None = None
    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    ctr: float | None = None
    conversions: int = Field(default=0, ge=0)
    conversion_rate: float | None = None
    load_p75_ms: int | None = Field(default=None, ge=0)
    weight_saved_pct: float | None = None
    segment_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    trend: dict[str, Any] = Field(default_factory=dict)


class PerformanceSnapshotResponse(BaseModel):
    id: str
    campaign_id: str
    revision_id: str | None = None
    source: str = "manual"
    window_start: str | None = None
    window_end: str | None = None
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    conversions: int = 0
    conversion_rate: float = 0.0
    load_p75_ms: int | None = None
    weight_saved_pct: float | None = None
    segment_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    trend: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    live_analytics: bool = False
    data_source_label: str = NON_LIVE_LABEL

    @model_validator(mode="after")
    def label_live_imports(self) -> "PerformanceSnapshotResponse":
        if self.source in LIVE_SOURCES:
            self.live_analytics = True
            self.data_source_label = LIVE_SOURCE_LABEL
        return self


class OptimizationInsightResponse(BaseModel):
    id: str
    team_id: str | None = None
    campaign_id: str | None = None
    segment_key: str | None = None
    tag: str
    insight: str
    lift_label: str | None = None
    source: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    live_analytics: bool = False
    data_source_label: str = NON_LIVE_LABEL


class OptimizationProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_revision_id: str = Field(pattern=UUID_PATTERN)
    proposed_revision_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    segment_key: str | None = Field(default=None, max_length=120)
    rationale: str = Field(min_length=1, max_length=2000)
    projected_lift: dict[str, Any] = Field(default_factory=dict)
    status: ProposalStatus = "draft"


class OptimizationProposalResponse(BaseModel):
    id: str
    campaign_id: str
    source_revision_id: str
    proposed_revision_id: str | None = None
    segment_key: str | None = None
    rationale: str
    projected_lift: dict[str, Any] = Field(default_factory=dict)
    status: ProposalStatus = "draft"
    created_at: str | None = None
    updated_at: str | None = None
    live_analytics: bool = False
    data_source_label: str = NON_LIVE_LABEL


class CampaignPerformanceResponse(BaseModel):
    campaign_id: str
    latest_snapshot: PerformanceSnapshotResponse | None = None
    snapshots: list[PerformanceSnapshotResponse] = Field(default_factory=list)
    insights: list[OptimizationInsightResponse] = Field(default_factory=list)
    proposals: list[OptimizationProposalResponse] = Field(default_factory=list)
    live_analytics: bool = False
    data_source_label: str = NON_LIVE_LABEL
    metrics_note: str = NON_LIVE_NOTE
