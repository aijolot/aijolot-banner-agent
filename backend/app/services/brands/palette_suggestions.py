from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.agents.tools import gemini_text
from app.schemas.brand import BrandContext, BrandColorRole, _normalize_hex
from app.schemas.palette_suggestions import (
    PaletteSuggestion,
    PaletteSuggestionResponse,
    PaletteSuggestionRouteRequest,
)


class PaletteSuggestionUnavailable(RuntimeError):
    """Raised when Gemini cannot provide usable palette suggestions."""


class _GeminiPaletteSuggestion(BaseModel):
    name: str = Field(..., min_length=1)
    hex: str
    usage_hint: str = ""
    rationale: str = ""


class _GeminiPaletteSuggestionPayload(BaseModel):
    suggestions: list[_GeminiPaletteSuggestion] = Field(default_factory=list)


def _role_for(brand: BrandContext, role_key: str) -> BrandColorRole:
    if brand.color_system is None:  # BrandContext normally populates this.
        brand = BrandContext(**brand.model_dump())
    assert brand.color_system is not None
    return getattr(brand.color_system, role_key)


def _brand_prompt_snapshot(brand: BrandContext) -> dict[str, Any]:
    color_system = brand.color_system.model_dump() if brand.color_system is not None else None
    return {
        "id": brand.id,
        "name": brand.name,
        "palette": [color.model_dump() for color in brand.palette],
        "color_system": color_system,
        "voice_tone": brand.voice.tone,
        "required_phrases": brand.voice.required_phrases,
        "prohibited_words": brand.voice.prohibited_words,
        "image_style_directives": brand.image_style_directives,
        "notes": brand.notes,
    }


def build_palette_suggestion_prompt(
    *,
    brand: BrandContext,
    selected_role: BrandColorRole,
    base_hex: str,
    count: int,
    intent: str,
) -> str:
    snapshot = _brand_prompt_snapshot(brand)
    selected_role_payload = selected_role.model_dump()
    return (
        "You are a senior ecommerce brand designer. Generate Gemini-backed color suggestions "
        "for a Shopify banner design system.\n"
        "Return strict JSON matching this schema: "
        '{"suggestions":[{"name":"short color name","hex":"#RRGGBB","usage_hint":"where to use it","rationale":"why it fits"}]}.\n'
        "Rules:\n"
        f"- Suggest exactly {count} usable colors if possible.\n"
        "- Every hex must be a valid six-digit #RRGGBB color.\n"
        "- Do not repeat current role colors or variants unless the color is essential.\n"
        "- Keep names concise and usage hints specific to ecommerce banners.\n"
        "- Respect the selected role, brand voice, image directives, and user intent.\n\n"
        f"Selected role key: {selected_role.key}\n"
        f"Selected role label: {selected_role.label}\n"
        f"Selected role base hex: {base_hex}\n"
        f"Selected role usage hint: {selected_role.usage_hint}\n"
        f"Selected role agent hint: {selected_role.agent_hint}\n"
        f"Usage intent: {intent or 'General brand palette exploration for banners'}\n\n"
        "Selected role current variants JSON:\n"
        f"{json.dumps([variant.model_dump() for variant in selected_role.variants], ensure_ascii=False)}\n\n"
        "Full draft/persisted brand context JSON:\n"
        f"{json.dumps(snapshot, ensure_ascii=False)}"
    )


def _coerce_gemini_payload(result: Any) -> _GeminiPaletteSuggestionPayload:
    if isinstance(result, _GeminiPaletteSuggestionPayload):
        return result
    if isinstance(result, BaseModel):
        return _GeminiPaletteSuggestionPayload.model_validate(result.model_dump())
    if isinstance(result, str):
        try:
            return _GeminiPaletteSuggestionPayload.model_validate(json.loads(result))
        except Exception as exc:  # noqa: BLE001
            raise PaletteSuggestionUnavailable("Gemini palette response could not be parsed") from exc
    try:
        return _GeminiPaletteSuggestionPayload.model_validate(result)
    except Exception as exc:  # noqa: BLE001
        raise PaletteSuggestionUnavailable("Gemini palette response could not be parsed") from exc


def _filtered_suggestions(
    payload: _GeminiPaletteSuggestionPayload,
    *,
    selected_role: BrandColorRole,
    base_hex: str,
    count: int,
) -> list[PaletteSuggestion]:
    existing_hexes = {base_hex.upper(), selected_role.hex.upper()}
    existing_hexes.update(variant.hex.upper() for variant in selected_role.variants)
    seen_hexes: set[str] = set()
    suggestions: list[PaletteSuggestion] = []
    for item in payload.suggestions:
        try:
            hex_value = _normalize_hex(item.hex)
        except ValueError:
            continue
        if hex_value in seen_hexes or hex_value in existing_hexes:
            continue
        seen_hexes.add(hex_value)
        suggestions.append(
            PaletteSuggestion(
                name=item.name.strip(),
                hex=hex_value,
                usage_hint=item.usage_hint.strip(),
                rationale=item.rationale.strip(),
            )
        )
        if len(suggestions) >= count:
            break
    return suggestions


class PaletteSuggestionService:
    def __init__(self, brand_service: Any) -> None:
        self.brand_service = brand_service

    async def suggest(
        self,
        brand_id: str,
        request: PaletteSuggestionRouteRequest,
    ) -> PaletteSuggestionResponse:
        persisted_brand = self.brand_service.get_brand(brand_id)
        brand = request.draft_brand_context or persisted_brand
        selected_role = _role_for(brand, request.role_key)
        base_hex = request.base_hex or selected_role.hex
        base_hex = _normalize_hex(base_hex)
        prompt = build_palette_suggestion_prompt(
            brand=brand,
            selected_role=selected_role,
            base_hex=base_hex,
            count=request.count,
            intent=request.intent,
        )
        try:
            result = await gemini_text.generate(
                prompt,
                model=gemini_text.FLASH_MODEL,
                structured=_GeminiPaletteSuggestionPayload,
            )
        except gemini_text.GeminiUnavailable as exc:
            raise PaletteSuggestionUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise PaletteSuggestionUnavailable(f"Gemini palette suggestion failed: {exc.__class__.__name__}") from exc

        payload = _coerce_gemini_payload(result)
        suggestions = _filtered_suggestions(payload, selected_role=selected_role, base_hex=base_hex, count=request.count)
        if not suggestions:
            raise PaletteSuggestionUnavailable("Gemini returned no valid palette suggestions")
        return PaletteSuggestionResponse(
            role_key=request.role_key,
            base_hex=base_hex,
            source="gemini",
            suggestions=suggestions,
        )
