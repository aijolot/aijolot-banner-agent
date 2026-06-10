from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.brand import BrandContext, _normalize_hex

BrandColorRoleKey = Literal["primary", "secondary", "tertiary"]


class PaletteSuggestionRouteRequest(BaseModel):
    role_key: BrandColorRoleKey
    base_hex: str | None = None
    count: int = Field(default=8, ge=3, le=12)
    intent: str = ""
    draft_brand_context: BrandContext | None = None

    @field_validator("base_hex")
    @classmethod
    def _valid_base_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_hex(value)


class PaletteSuggestion(BaseModel):
    name: str = Field(..., min_length=1)
    hex: str
    usage_hint: str = ""
    rationale: str = ""

    @field_validator("hex")
    @classmethod
    def _valid_hex(cls, value: str) -> str:
        return _normalize_hex(value)


class PaletteSuggestionResponse(BaseModel):
    role_key: str
    base_hex: str
    source: Literal["gemini"] = "gemini"
    suggestions: list[PaletteSuggestion]
