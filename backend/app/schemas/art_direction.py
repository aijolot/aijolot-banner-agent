from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BackgroundMode = Literal["hero", "usage"]
CreativeMode = Literal["composite", "full_picture", "video"]
ModeSource = Literal["agent", "user"]
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class ArtDirectionUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background_mode: BackgroundMode
    hero_style_key: str | None = None
    model_key: str | None = None
    custom_model: dict[str, Any] = Field(default_factory=dict)
    fold_percentage: int = Field(default=55, ge=0, le=100)
    layout_hints: dict[str, Any] = Field(default_factory=dict)
    # C0 — creative mode: agent-recommended, user-overridable (mode_source='user'
    # is authoritative and never overwritten by a re-recommendation).
    creative_mode: CreativeMode = "composite"
    include_humans: bool = False
    mode_rationale: str | None = None
    mode_source: ModeSource = "agent"

    @model_validator(mode="after")
    def _normalize_blank_strings(self) -> "ArtDirectionUpsert":
        for field_name in ("hero_style_key", "model_key"):
            value = getattr(self, field_name)
            if isinstance(value, str):
                stripped = value.strip()
                setattr(self, field_name, stripped or None)
        return self


class ArtDirectionResponse(ArtDirectionUpsert):
    id: str
    campaign_id: str = Field(..., pattern=UUID_PATTERN)
    created_at: str | None = None
    updated_at: str | None = None
