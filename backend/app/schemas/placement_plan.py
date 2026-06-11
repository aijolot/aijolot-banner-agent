"""Placement plan proposal (the agent suggests WHERE/HOW MANY/WHAT FORMAT).

The placement stops being a manual pre-step: the plan phase proposes a set of
pieces (placement + format + creative mode + rationale) derived from the brief.
Piece 1 (priority 1) is what the approve/build generates now; the rest are the
campaign's suggested roadmap.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PlacementPiece(BaseModel):
    placement_key: str = Field(description="placement_types key, e.g. hero_main")
    label: str = ""
    target: str = Field(default="home", description="home | collection | product | search | page | store")
    slot: str = ""
    format: str = Field(default="", description="Human format, e.g. '1440×420px (desktop)'")
    creative_mode: str = Field(default="composite", description="composite | full_picture | video")
    priority: int = Field(default=1, ge=1, le=9)
    rationale: str = ""

    @field_validator("creative_mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        cleaned = (v or "").strip().lower()
        return cleaned if cleaned in ("composite", "full_picture", "video") else "composite"


class PlacementPlanProposal(BaseModel):
    pieces: list[PlacementPiece] = Field(default_factory=list)
    rationale: str = ""
    source: str = Field(default="deterministic", description="'gemini' | 'deterministic'")
