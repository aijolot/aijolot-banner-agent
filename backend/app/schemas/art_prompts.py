"""Schemas for descriptive art/model prompt proposals + art generation (F8)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ShotType = Literal["hero", "usage"]
USAGE_ANGLES: tuple[str, ...] = ("front", "three_quarter", "top_down", "in_use")


class PromptOption(BaseModel):
    """One proposed image prompt (text only — generation is a separate step)."""

    label: str = Field(description="Short label, e.g. 'A', 'B', 'C'")
    description: str = Field(default="", description="One-line summary of the look")
    prompt: str = Field(description="Sanitized image-generation prompt")
    angle: str | None = Field(default=None, description="Camera angle for usage shots")
    background_ref: str | None = Field(default=None, description="Background option name/ref from F7")


class PromptOptionsOutput(BaseModel):
    """Structured output contract for the Gemini proposal call."""

    options: list[PromptOption] = Field(default_factory=list)


class ArtPromptsRequest(BaseModel):
    shot_type: ShotType = "hero"
    count: int = Field(default=3, ge=1, le=4)
    revision_id: str | None = None
    background_ref: str | None = None


class ModelPromptsRequest(BaseModel):
    gender: str = ""
    prompt: str = ""
    count: int = Field(default=3, ge=1, le=4)
    revision_id: str | None = None


class ArtPromptsResponse(BaseModel):
    campaign_id: str
    revision_id: str | None = None
    shot_type: ShotType = "hero"
    source: str = "deterministic"  # "gemini" | "deterministic"
    options: list[PromptOption] = Field(default_factory=list)


class GenerateArtRequest(BaseModel):
    prompt: str = ""
    label: str | None = None
    shot_type: ShotType = "hero"
    background_ref: str | None = None
    background_css: str | None = None
    aspect_ratio: str = "16:9"
    revision_id: str | None = None


class GeneratedAsset(BaseModel):
    storage_path: str | None = None
    public_url: str | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None
    size_key: int | None = None
    bytes: int | None = None


class GenerateArtResponse(BaseModel):
    campaign_id: str
    revision_id: str | None = None
    shot_type: ShotType = "hero"
    provider: str | None = None
    prompt: str = ""
    asset: GeneratedAsset | None = None
    assets: list[GeneratedAsset] = Field(default_factory=list)
    background_ref: str | None = None
    composed_html: str | None = None
    cost_usd: float = 0.0
