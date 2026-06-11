"""Gemini-backed font suggestions with an explicitly non-AI fallback (Task 6).

``FontSuggestionService.suggest`` returns three clearly separated buckets:

- ``discovered``: deterministic candidates mapped from the brand's latest
  discovery snapshot (``shopify_theme`` / ``storefront_css``), never AI.
- ``suggestions``: Gemini-backed candidates (``gemini_suggested``), only populated
  when Gemini actually answered with usable fonts.
- ``seeds``: the curated ``system_seed`` pool.

AI honesty contract: unlike palette/color recommendations this endpoint does NOT
503 when Gemini is down. Per the plan, deterministic seed fonts are an allowed
fallback as long as they are explicitly labeled non-AI - so the fallback response
says ``source="deterministic_fallback"``, ``ai_available=False``, leaves
``suggestions`` empty, and keeps the deterministic buckets. Seeds/discovered fonts
are never relabeled as AI output.

Nothing returned here is auto-approved: every candidate keeps
``status="candidate"`` until the user applies it (Task 7).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.agents.tools import gemini_text
from app.schemas.brand import BrandContext, FontCandidate, FontRoleKey, Typography
from app.services.brands.font_discovery import (
    SYSTEM_SEED_FONTS,
    build_css_stack,
    font_candidates_from_snapshot,
    guess_font_category,
)

__all__ = [
    "FONT_ROLE_SEMANTICS",
    "FontSuggestionResponse",
    "FontSuggestionRouteRequest",
    "FontSuggestionService",
    "build_font_suggestion_prompt",
]

FONT_ROLE_SEMANTICS: dict[str, str] = {
    "display": "Largest hero/display type for the dominant banner statement.",
    "headline": "Headlines and section titles below the hero moment.",
    "body": "Paragraph and supporting copy; must stay readable at small sizes.",
    "accent": "Short emphasis moments: badges, prices, discount codes, stylistic accents.",
    "caption": "Smallest text: captions, legal lines, fine print.",
}

_VALID_ROLE_KEYS: tuple[str, ...] = tuple(FONT_ROLE_SEMANTICS)
_VALID_CATEGORIES = {"sans", "serif", "display", "mono", "handwritten", "unknown"}


# -- request/response contracts ------------------------------------------------------


class FontSuggestionRouteRequest(BaseModel):
    count: int = Field(default=8, ge=3, le=16)
    intent: str = ""
    include_discovered: bool = True
    include_seeds: bool = True
    draft_brand_context: BrandContext | None = None


class FontSuggestionResponse(BaseModel):
    source: Literal["gemini", "deterministic_fallback"]
    ai_available: bool
    message: str
    discovered: list[FontCandidate] = Field(default_factory=list)
    suggestions: list[FontCandidate] = Field(default_factory=list)
    seeds: list[FontCandidate] = Field(default_factory=list)


# -- tolerant Gemini payload models --------------------------------------------------
# Mirror FontCandidate but accept sloppy output; conversion enforces the strict schema.


class _GeminiFontSuggestion(BaseModel):
    family: str = ""
    css_stack: str = ""
    category: str = ""
    recommended_roles: list[str] = Field(default_factory=list)
    rationale: str = ""

    @field_validator("family", "css_stack", "category", "rationale", mode="before")
    @classmethod
    def _none_to_empty(cls, value: Any) -> Any:
        return "" if value is None else value

    @field_validator("recommended_roles", mode="before")
    @classmethod
    def _none_to_list(cls, value: Any) -> Any:
        return [] if value is None else value


class _GeminiFontSuggestionPayload(BaseModel):
    suggestions: list[_GeminiFontSuggestion] = Field(default_factory=list)

    @field_validator("suggestions", mode="before")
    @classmethod
    def _none_to_list(cls, value: Any) -> Any:
        return [] if value is None else value


# -- prompt ---------------------------------------------------------------------------


def _typography_summary(typography: Typography) -> dict[str, Any]:
    return {
        "display": typography.display,
        "body": typography.body,
        "headline": typography.headline,
        "accent": typography.accent,
        "approved_fonts": [
            {"family": font.family, "category": font.category, "recommended_roles": font.recommended_roles}
            for font in typography.approved_fonts
        ],
        "discarded_fonts": [font.family for font in typography.discarded_fonts],
    }


def build_font_suggestion_prompt(
    *,
    brand: BrandContext,
    discovered: list[FontCandidate],
    count: int,
    intent: str,
) -> str:
    discovered_summary = [
        {"family": font.family, "category": font.category, "source": font.source, "evidence_refs": font.evidence_refs}
        for font in discovered
    ]
    seed_families = [seed.family for seed in SYSTEM_SEED_FONTS]
    discarded_families = [font.family for font in brand.typography.discarded_fonts]
    return (
        "You are a senior ecommerce brand typographer. Recommend font families for a "
        "Shopify banner design system.\n"
        "Return strict JSON matching this schema: "
        '{"suggestions":[{"family":"single font family name","css_stack":"family plus safe fallbacks","category":"sans|serif|display|mono|handwritten|unknown",'
        '"recommended_roles":["display|headline|body|accent|caption"],'
        '"rationale":"why it fits this brand, including a pairing/compatibility note"}]}.\n'
        "Rules:\n"
        f"- Suggest exactly {count} font families if possible.\n"
        "- family must be a plain font family name: letters, digits, spaces and hyphens only.\n"
        "- css_stack must contain only family names, commas and quotes; end it with a generic "
        "family such as sans-serif, serif, monospace or cursive.\n"
        "- Prefer the discovered storefront fonts and the allowed safe pool below; you may add "
        "other widely available Google Fonts when they clearly fit the brand.\n"
        "- NEVER suggest a font family the user already discarded.\n"
        "- Do not repeat a discovered family as a new suggestion; suggest complements/pairings instead.\n"
        "- Fold pairing/compatibility guidance into each rationale (what it pairs with and for which roles).\n"
        "- Respect the brand voice, image directives and the user intent.\n\n"
        "Font role semantics:\n"
        f"{json.dumps(FONT_ROLE_SEMANTICS, ensure_ascii=False)}\n\n"
        f"User intent: {intent or 'General typography exploration for banner generation'}\n\n"
        f"Brand name: {brand.name}\n"
        f"Brand voice tone: {json.dumps(brand.voice.tone, ensure_ascii=False)}\n"
        f"Brand image directives: {json.dumps(brand.image_style_directives, ensure_ascii=False)}\n\n"
        "Current typography (approved fonts are user-approved; NEVER re-suggest the discarded families):\n"
        f"{json.dumps(_typography_summary(brand.typography), ensure_ascii=False)}\n"
        f"Discarded families (forbidden): {json.dumps(discarded_families, ensure_ascii=False)}\n\n"
        "Fonts discovered in the live storefront/theme (with provenance):\n"
        f"{json.dumps(discovered_summary, ensure_ascii=False)}\n\n"
        "Allowed safe pool (curated, widely available; you may draw from it):\n"
        f"{json.dumps(seed_families, ensure_ascii=False)}"
    )


# -- parsing / conversion -------------------------------------------------------------


def _coerce_gemini_payload(result: Any) -> _GeminiFontSuggestionPayload | None:
    """Best-effort payload coercion; None means unusable (fallback, not 503)."""

    if isinstance(result, _GeminiFontSuggestionPayload):
        return result
    if isinstance(result, BaseModel):
        result = result.model_dump()
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:  # noqa: BLE001
            return None
    try:
        return _GeminiFontSuggestionPayload.model_validate(result)
    except Exception:  # noqa: BLE001
        return None


def _safe_roles(raw_roles: list[str]) -> list[FontRoleKey]:
    roles: list[FontRoleKey] = []
    for raw in raw_roles:
        role = str(raw or "").strip().lower()
        if role in _VALID_ROLE_KEYS and role not in roles:
            roles.append(role)  # type: ignore[arg-type]
    return roles


def _candidate_from_gemini_item(item: _GeminiFontSuggestion) -> FontCandidate | None:
    family = " ".join(item.family.split())
    if not family:
        return None
    category = item.category.strip().lower()
    if category not in _VALID_CATEGORIES:
        category = guess_font_category(family)
    css_stack = item.css_stack.strip()
    try:
        return FontCandidate(
            family=family,
            css_stack=css_stack or build_css_stack(family, category),
            category=category,  # type: ignore[arg-type]
            source="gemini_suggested",
            status="candidate",
            recommended_roles=_safe_roles(item.recommended_roles),
            rationale=item.rationale.strip(),
            evidence_refs=[],
        )
    except ValueError:
        # Unsafe family/css_stack (whitelist) - drop and retry once with a built stack,
        # so one bad AI css_stack does not discard an otherwise valid family.
        if css_stack:
            try:
                return FontCandidate(
                    family=family,
                    css_stack=build_css_stack(family, category),
                    category=category,  # type: ignore[arg-type]
                    source="gemini_suggested",
                    status="candidate",
                    recommended_roles=_safe_roles(item.recommended_roles),
                    rationale=item.rationale.strip(),
                    evidence_refs=[],
                )
            except ValueError:
                return None
        return None


def _filtered_suggestions(
    payload: _GeminiFontSuggestionPayload,
    *,
    count: int,
    blocked_families: set[str],
) -> list[FontCandidate]:
    """Strict candidates, deduped against blocked families (discovered/approved/discarded)."""

    seen = set(blocked_families)
    suggestions: list[FontCandidate] = []
    for item in payload.suggestions:
        candidate = _candidate_from_gemini_item(item)
        if candidate is None:
            continue
        key = candidate.family.lower()
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(candidate)
        if len(suggestions) >= count:
            break
    return suggestions


# -- service --------------------------------------------------------------------------


class FontSuggestionService:
    def __init__(self, brand_service: Any) -> None:
        self.brand_service = brand_service

    async def suggest(self, brand_id: str, request: FontSuggestionRouteRequest) -> FontSuggestionResponse:
        persisted_brand = self.brand_service.get_brand(brand_id)  # BrandNotFound propagates to the route
        brand = request.draft_brand_context or persisted_brand

        discovered: list[FontCandidate] = []
        if request.include_discovered:
            snapshot = self.brand_service.get_discovery_snapshot(brand_id)  # None in markdown/demo mode
            if snapshot is not None:
                discovered = font_candidates_from_snapshot(snapshot)

        discarded_families = {font.family.lower() for font in brand.typography.discarded_fonts}
        approved_families = {font.family.lower() for font in brand.typography.approved_fonts}
        blocked_families = (
            discarded_families | approved_families | {font.family.lower() for font in discovered}
        )

        prompt = build_font_suggestion_prompt(
            brand=brand, discovered=discovered, count=request.count, intent=request.intent
        )
        try:
            result = await gemini_text.generate(
                prompt,
                model=gemini_text.FLASH_MODEL,
                structured=_GeminiFontSuggestionPayload,
            )
        except gemini_text.GeminiUnavailable as exc:
            return self._fallback(request, discovered=discovered, discarded=discarded_families, approved=approved_families, reason=str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._fallback(
                request,
                discovered=discovered,
                discarded=discarded_families,
                approved=approved_families,
                reason=f"Gemini font suggestion failed: {exc.__class__.__name__}",
            )

        payload = _coerce_gemini_payload(result)
        if payload is None:
            return self._fallback(
                request,
                discovered=discovered,
                discarded=discarded_families,
                approved=approved_families,
                reason="Gemini font response could not be parsed",
            )
        suggestions = _filtered_suggestions(payload, count=request.count, blocked_families=blocked_families)
        if not suggestions:
            return self._fallback(
                request,
                discovered=discovered,
                discarded=discarded_families,
                approved=approved_families,
                reason="Gemini returned no usable font suggestions",
            )

        suggested_families = {candidate.family.lower() for candidate in suggestions}
        seeds = self._seeds(request, exclude=discarded_families | approved_families | suggested_families)
        return FontSuggestionResponse(
            source="gemini",
            ai_available=True,
            message=f"Gemini returned {len(suggestions)} font suggestions.",
            discovered=discovered,
            suggestions=suggestions,
            seeds=seeds,
        )

    @staticmethod
    def _seeds(request: FontSuggestionRouteRequest, *, exclude: set[str]) -> list[FontCandidate]:
        """Curated seed copies; never re-offer families the user already settled."""

        if not request.include_seeds:
            return []
        return [
            seed.model_copy(deep=True)
            for seed in SYSTEM_SEED_FONTS
            if seed.family.lower() not in exclude
        ]

    def _fallback(
        self,
        request: FontSuggestionRouteRequest,
        *,
        discovered: list[FontCandidate],
        discarded: set[str],
        approved: set[str],
        reason: str,
    ) -> FontSuggestionResponse:
        """Explicitly labeled non-AI response: no fake suggestions, ever."""

        return FontSuggestionResponse(
            source="deterministic_fallback",
            ai_available=False,
            message=(
                f"AI font suggestions are unavailable ({reason}). "
                "The fonts below are curated non-AI seed candidates and deterministic "
                "storefront discoveries, not AI recommendations."
            ),
            discovered=discovered,
            suggestions=[],
            seeds=self._seeds(request, exclude=discarded | approved),
        )
