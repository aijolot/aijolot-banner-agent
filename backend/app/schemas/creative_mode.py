"""Creative mode recommendation schema (C0)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

CREATIVE_MODES = ("composite", "full_picture", "video")


class CreativeModeRecommendation(BaseModel):
    """Agent-recommended creative mode for a campaign banner."""

    creative_mode: str = Field(default="composite", description="composite | full_picture | video")
    include_humans: bool = False
    rationale: str = ""
    source: str = Field(default="deterministic", description="'gemini' | 'deterministic' | 'user'")

    @field_validator("creative_mode")
    @classmethod
    def _valid_mode(cls, v: str) -> str:
        cleaned = (v or "").strip().lower()
        return cleaned if cleaned in CREATIVE_MODES else "composite"
