"""Schemas for AI-generated banner background options (F7)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BackgroundOption(BaseModel):
    """One self-contained background treatment for the `.aijolot-banner` surface."""

    name: str = Field(description="Short human label, e.g. 'Sunset gradient'")
    description: str = Field(description="One-line description of the look")
    css: str = Field(description="Self-contained CSS scoped to .aijolot-banner, no external assets")
    html: str = Field(default="", description="Optional minimal HTML wrapper for the banner surface")
    rationale: str = Field(default="", description="Why this fits the brand/concept")


class BackgroundOptionsOutput(BaseModel):
    """Structured output contract for the Gemini generation call."""

    options: list[BackgroundOption] = Field(default_factory=list)


class BackgroundOptionsRequest(BaseModel):
    revision_id: str | None = None
    count: int = Field(default=3, ge=1, le=5)


class BackgroundOptionsResponse(BaseModel):
    campaign_id: str
    revision_id: str | None = None
    source: str = "deterministic"  # "gemini" | "deterministic"
    options: list[BackgroundOption] = Field(default_factory=list)
