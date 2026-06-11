"""Gemini-backed brand color recommendations from discovery evidence (Task 5).

Converts one brand's :class:`BrandDiscoverySnapshot` (raw Shopify evidence) into a
:class:`BrandRecommendationDraft` of color roles. The draft never auto-applies:
Task 7 writes accepted items onto ``BrandContext.color_system`` explicitly.

AI honesty contract: recommendations are always Gemini-backed. When Gemini is
unavailable or returns nothing usable the service raises
:class:`BrandRecommendationUnavailable` (routes map it to 503) instead of
fabricating a deterministic palette. The only non-AI content in a draft is the
per-role backfill from the user's own already-approved color system when Gemini
answers with fewer than three roles, labeled with a fixed rationale.

``BrandRecommendationDraft.fonts`` stays empty here; Task 6 adds font candidates.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agents.tools import gemini_text
from app.schemas.brand import (
    ROLE_DEFAULTS,
    BrandColorRole,
    BrandColorVariant,
    BrandContext,
    _normalize_hex,
)
from app.schemas.brand_discovery import (
    BrandColorRecommendation,
    BrandDiscoverySnapshot,
    BrandRecommendationDraft,
)

__all__ = [
    "BrandRecommendationService",
    "BrandRecommendationUnavailable",
    "build_color_recommendation_prompt",
]

_ROLE_KEYS = ("primary", "secondary", "tertiary")
_BACKFILL_RATIONALE = "kept from existing approved brand context"
_MAX_VARIANTS_PER_ROLE = 6
_MAX_EVIDENCE_REFS = 8
_MAX_ASSET_URLS_IN_PROMPT = 12


class BrandRecommendationUnavailable(RuntimeError):
    """Raised when Gemini cannot provide usable brand color recommendations."""


# -- tolerant Gemini payload models ------------------------------------------------
# Mirror BrandColorRecommendation but accept sloppy output (missing/None fields,
# bad hexes, unknown role keys). Conversion below enforces the strict schema.


class _GeminiRecommendedVariant(BaseModel):
    name: str = ""
    hex: str = ""
    usage_hint: str = ""

    @field_validator("name", "hex", "usage_hint", mode="before")
    @classmethod
    def _none_to_empty(cls, value: Any) -> Any:
        return "" if value is None else value


class _GeminiRecommendedColor(BaseModel):
    role_key: str = ""
    base_hex: str = ""
    label: str = ""
    usage_hint: str = ""
    agent_hint: str = ""
    variants: list[_GeminiRecommendedVariant] = Field(default_factory=list)
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("role_key", "base_hex", "label", "usage_hint", "agent_hint", "rationale", mode="before")
    @classmethod
    def _none_to_empty(cls, value: Any) -> Any:
        return "" if value is None else value

    @field_validator("variants", "evidence_refs", mode="before")
    @classmethod
    def _none_to_list(cls, value: Any) -> Any:
        return [] if value is None else value


class _GeminiRecommendationPayload(BaseModel):
    colors: list[_GeminiRecommendedColor] = Field(default_factory=list)
    summary: str = ""

    @field_validator("colors", mode="before")
    @classmethod
    def _none_to_list(cls, value: Any) -> Any:
        return [] if value is None else value

    @field_validator("summary", mode="before")
    @classmethod
    def _none_to_empty(cls, value: Any) -> Any:
        return "" if value is None else value


# -- prompt -------------------------------------------------------------------------


def _existing_role(brand: BrandContext, role_key: str) -> BrandColorRole:
    if brand.color_system is None:  # BrandContext normally populates this on validation.
        brand = BrandContext(**brand.model_dump())
    assert brand.color_system is not None
    return getattr(brand.color_system, role_key)


def _metadata_summary(snapshot: BrandDiscoverySnapshot) -> dict[str, Any]:
    theme_metadata = snapshot.theme_metadata if isinstance(snapshot.theme_metadata, dict) else {}
    return {
        "shop_domain": snapshot.shop_domain,
        "shop_name": str(theme_metadata.get("shop_name") or ""),
        "brand_slogan": str(theme_metadata.get("brand_slogan") or ""),
        "theme_name": str(theme_metadata.get("theme_name") or ""),
        "source_summary": snapshot.source_summary,
    }


def _asset_summary(snapshot: BrandDiscoverySnapshot) -> dict[str, Any]:
    counts = Counter(asset.kind for asset in snapshot.assets)
    urls = [
        {"kind": asset.kind, "url": asset.url, "source": asset.source}
        for asset in snapshot.assets
        if asset.kind in ("logo", "banner", "hero") and asset.url
    ]
    return {"counts": dict(counts), "logo_banner_hero_urls": urls[:_MAX_ASSET_URLS_IN_PROMPT]}


def build_color_recommendation_prompt(*, brand: BrandContext, snapshot: BrandDiscoverySnapshot) -> str:
    discovered = [
        {
            "hex": color.hex,
            "name": color.name,
            "source": color.source,
            "confidence": color.confidence,
            "usage_hint": color.usage_hint,
        }
        for color in sorted(snapshot.colors, key=lambda color: color.confidence, reverse=True)
    ]
    existing_color_system = {key: _existing_role(brand, key).model_dump() for key in _ROLE_KEYS}
    return (
        "You are a senior ecommerce brand designer. Convert Shopify brand discovery evidence "
        "into recommended brand color roles for a banner design system.\n"
        "Return strict JSON matching this schema: "
        '{"colors":[{"role_key":"primary|secondary|tertiary","base_hex":"#RRGGBB",'
        '"label":"short role label","usage_hint":"where to use it",'
        '"agent_hint":"guidance for the generation agent",'
        '"variants":[{"name":"short variant name","hex":"#RRGGBB","usage_hint":"where to use it"}],'
        '"rationale":"why this fits the evidence",'
        '"evidence_refs":["source value of a discovered color used as evidence"]}],'
        '"summary":"1-2 sentence overview of the recommendation"}.\n'
        "Rules:\n"
        "- Recommend exactly one entry for each role_key: primary, secondary, tertiary.\n"
        "- Every hex must be a valid six-digit #RRGGBB color.\n"
        "- The existing approved brand color system below was approved by the user: respect it. "
        "Keep or refine an existing role color when the discovered evidence supports it, and only "
        "replace a role when the evidence is clearly stronger. Recommendations should improve the "
        "approved system, never silently discard it.\n"
        "- Prefer discovered colors with higher confidence and echo their exact source values in "
        "evidence_refs.\n"
        "- Always fill usage_hint, agent_hint and rationale with specific, non-empty text.\n\n"
        "Role semantics:\n"
        f"{json.dumps(ROLE_DEFAULTS, ensure_ascii=False)}\n\n"
        "Discovered colors (sorted by confidence, highest first):\n"
        f"{json.dumps(discovered, ensure_ascii=False)}\n\n"
        "Shop/theme metadata summary:\n"
        f"{json.dumps(_metadata_summary(snapshot), ensure_ascii=False)}\n\n"
        "Discovered asset summary:\n"
        f"{json.dumps(_asset_summary(snapshot), ensure_ascii=False)}\n\n"
        "Existing approved brand color system (refine, do not blindly overwrite):\n"
        f"{json.dumps(existing_color_system, ensure_ascii=False)}\n\n"
        f"Brand name: {brand.name}\n"
        f"Brand image directives: {json.dumps(brand.image_style_directives, ensure_ascii=False)}"
    )


# -- parsing / conversion -----------------------------------------------------------


def _coerce_gemini_payload(result: Any) -> _GeminiRecommendationPayload:
    if isinstance(result, _GeminiRecommendationPayload):
        return result
    if isinstance(result, BaseModel):
        return _GeminiRecommendationPayload.model_validate(result.model_dump())
    if isinstance(result, str):
        try:
            return _GeminiRecommendationPayload.model_validate(json.loads(result))
        except Exception as exc:  # noqa: BLE001
            raise BrandRecommendationUnavailable("Gemini brand recommendation response could not be parsed") from exc
    try:
        return _GeminiRecommendationPayload.model_validate(result)
    except Exception as exc:  # noqa: BLE001
        raise BrandRecommendationUnavailable("Gemini brand recommendation response could not be parsed") from exc


def _known_sources(snapshot: BrandDiscoverySnapshot) -> dict[str, str]:
    """Lowercased source -> canonical source string, from actual snapshot evidence."""

    canonical: dict[str, str] = {}
    sources = (
        [color.source for color in snapshot.colors]
        + [asset.source for asset in snapshot.assets]
        + [font.source for font in snapshot.fonts]
    )
    for source in sources:
        text = str(source or "").strip()
        if text:
            canonical.setdefault(text.lower(), text)
    return canonical


def _sources_by_hex(snapshot: BrandDiscoverySnapshot) -> dict[str, list[str]]:
    by_hex: dict[str, list[str]] = {}
    for color in snapshot.colors:
        sources = by_hex.setdefault(color.hex, [])
        if color.source and color.source not in sources:
            sources.append(color.source)
    return by_hex


def _evidence_refs(
    raw_refs: list[str],
    *,
    known_sources: dict[str, str],
    fallback_sources: list[str],
) -> list[str]:
    """Echoed refs, canonicalized against real snapshot sources (never trusted blindly).

    Refs matching actual evidence are rewritten to the canonical source string;
    everything else stays as free text. Without any usable echo, fall back to the
    snapshot sources that actually produced the recommended base hex.
    """

    refs: list[str] = []
    for raw in raw_refs:
        text = str(raw or "").strip()
        if not text:
            continue
        mapped = known_sources.get(text.lower(), text)
        if mapped not in refs:
            refs.append(mapped)
    if not refs:
        for source in fallback_sources:
            if source and source not in refs:
                refs.append(source)
    return refs[:_MAX_EVIDENCE_REFS]


def _recommendation_from_item(
    item: _GeminiRecommendedColor,
    *,
    role_key: str,
    existing_role: BrandColorRole,
    known_sources: dict[str, str],
    sources_by_hex: dict[str, list[str]],
) -> BrandColorRecommendation | None:
    try:
        base_hex = _normalize_hex(item.base_hex)
    except ValueError:
        return None
    label = item.label.strip() or existing_role.label or ROLE_DEFAULTS[role_key]["label"]
    variants: list[BrandColorVariant] = []
    seen_hexes = {base_hex}
    for index, raw_variant in enumerate(item.variants, start=1):
        try:
            hex_value = _normalize_hex(raw_variant.hex)
        except ValueError:
            continue
        if hex_value in seen_hexes:
            continue
        seen_hexes.add(hex_value)
        variants.append(
            BrandColorVariant(
                name=raw_variant.name.strip() or f"{label} variant {index}",
                hex=hex_value,
                usage_hint=raw_variant.usage_hint.strip(),
                source="gemini",
            )
        )
        if len(variants) >= _MAX_VARIANTS_PER_ROLE:
            break
    return BrandColorRecommendation(
        role_key=role_key,
        base_hex=base_hex,
        label=label,
        usage_hint=item.usage_hint.strip(),
        agent_hint=item.agent_hint.strip(),
        variants=variants,
        rationale=item.rationale.strip(),
        evidence_refs=_evidence_refs(
            item.evidence_refs,
            known_sources=known_sources,
            fallback_sources=sources_by_hex.get(base_hex, []),
        ),
    )


def _backfilled_recommendation(existing_role: BrandColorRole) -> BrandColorRecommendation:
    """Complete a missing role from the user's approved color system (not AI output)."""

    return BrandColorRecommendation(
        role_key=existing_role.key,
        base_hex=existing_role.hex,
        label=existing_role.label,
        usage_hint=existing_role.usage_hint,
        agent_hint=existing_role.agent_hint,
        variants=[variant.model_copy(deep=True) for variant in existing_role.variants],
        rationale=_BACKFILL_RATIONALE,
        evidence_refs=[],
    )


def _source_notes(snapshot: BrandDiscoverySnapshot) -> list[str]:
    """Snapshot source buckets that fed the prompt (e.g. theme_settings, css, section)."""

    notes: list[str] = []
    sources = [color.source for color in snapshot.colors] + [asset.source for asset in snapshot.assets]
    for source in sources:
        bucket = str(source or "").split(":", 1)[0].strip()
        if bucket and bucket not in notes:
            notes.append(bucket)
    if snapshot.theme_metadata and "theme_metadata" not in notes:
        notes.append("theme_metadata")
    return notes


# -- service ------------------------------------------------------------------------


class BrandRecommendationService:
    """Turn discovery evidence into a Gemini-backed color role recommendation draft."""

    async def recommend_colors(
        self, *, brand: BrandContext, snapshot: BrandDiscoverySnapshot
    ) -> BrandRecommendationDraft:
        prompt = build_color_recommendation_prompt(brand=brand, snapshot=snapshot)
        try:
            result = await gemini_text.generate(
                prompt,
                model=gemini_text.FLASH_MODEL,
                structured=_GeminiRecommendationPayload,
            )
        except gemini_text.GeminiUnavailable as exc:
            raise BrandRecommendationUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise BrandRecommendationUnavailable(
                f"Gemini brand recommendation failed: {exc.__class__.__name__}"
            ) from exc

        payload = _coerce_gemini_payload(result)
        known_sources = _known_sources(snapshot)
        sources_by_hex = _sources_by_hex(snapshot)
        by_role: dict[str, BrandColorRecommendation] = {}
        for item in payload.colors:
            role_key = item.role_key.strip().lower()
            if role_key not in _ROLE_KEYS or role_key in by_role:
                continue  # unknown role, or duplicate role_key (keep the first valid one)
            recommendation = _recommendation_from_item(
                item,
                role_key=role_key,
                existing_role=_existing_role(brand, role_key),
                known_sources=known_sources,
                sources_by_hex=sources_by_hex,
            )
            if recommendation is not None:
                by_role[role_key] = recommendation
        if not by_role:
            raise BrandRecommendationUnavailable("Gemini returned no valid color role recommendations")

        colors = [
            by_role.get(role_key) or _backfilled_recommendation(_existing_role(brand, role_key))
            for role_key in _ROLE_KEYS
        ]
        summary = payload.summary.strip() or (
            f"Color role recommendations from {len(snapshot.colors)} discovered colors"
        )
        return BrandRecommendationDraft(
            colors=colors,
            fonts=[],  # Task 6 adds font candidates here.
            summary=summary,
            source_notes=_source_notes(snapshot),
        )
