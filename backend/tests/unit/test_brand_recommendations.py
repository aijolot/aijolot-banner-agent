"""Unit tests for the Gemini brand color recommendation service (Task 5).

Mirrors the test style of ``test_palette_suggestions.py``: ``gemini_text.generate``
is monkeypatched on the service module, no network, no real Gemini.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.agents.tools import gemini_text
from app.schemas.brand import BrandContext
from app.schemas.brand_discovery import BrandDiscoverySnapshot
from app.services.brands import brand_recommendations as module
from app.services.brands.brand_recommendations import (
    BrandRecommendationService,
    BrandRecommendationUnavailable,
)

NAVY_SOURCE = "theme_settings:config/settings_data.json#colors_accent"
SAND_SOURCE = "css:assets/base.css"
CORAL_SOURCE = "section:sections/hero.liquid"


def _brand() -> BrandContext:
    return BrandContext.model_validate(
        {
            "id": "demo_brand",
            "name": "Demo Apparel",
            "palette": [
                {"name": "Ink", "hex": "#112233"},
                {"name": "Paper", "hex": "#F5E8D0"},
                {"name": "CTA", "hex": "#FF6655"},
            ],
            "color_system": {
                "primary": {
                    "key": "primary",
                    "label": "Hero Ink",
                    "hex": "#112233",
                    "usage_hint": "Use for hero headlines.",
                    "agent_hint": "Dominant visual anchor.",
                    "variants": [
                        {"name": "Hero Ink Soft", "hex": "#223344", "usage_hint": "Muted hero panels."}
                    ],
                },
                "secondary": {
                    "key": "secondary",
                    "label": "Warm Paper",
                    "hex": "#F5E8D0",
                    "usage_hint": "Use for backgrounds.",
                    "agent_hint": "Support the primary.",
                    "variants": [{"name": "Paper Deep", "hex": "#E3D2B4", "usage_hint": "Footer bands."}],
                },
                "tertiary": {
                    "key": "tertiary",
                    "label": "Coral CTA",
                    "hex": "#FF6655",
                    "usage_hint": "Use for CTA buttons.",
                    "agent_hint": "Apply sparingly.",
                    "variants": [],
                },
            },
            "image_style_directives": ["natural light", "premium product photography"],
            "shopify": {"store_domain": "demo-apparel.myshopify.com"},
        }
    )


def _snapshot() -> BrandDiscoverySnapshot:
    return BrandDiscoverySnapshot(
        id="disc_abc123def456",
        brand_id="demo_brand",
        shop_domain="demo-apparel.myshopify.com",
        status="succeeded",
        discovered_at=datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc),
        source_summary="theme: Dawn (id 99)",
        assets=[
            {"kind": "logo", "url": "https://cdn.shopify.com/logo.png", "source": "shop_metadata"},
            {"kind": "hero", "url": "https://cdn.shopify.com/hero.jpg", "source": CORAL_SOURCE},
        ],
        colors=[
            {"hex": "#0E1A2B", "name": "Deep Navy", "source": NAVY_SOURCE, "confidence": 0.95, "usage_hint": "Buttons"},
            {"hex": "#F4EDE2", "name": "Sand", "source": SAND_SOURCE, "confidence": 0.6},
            {"hex": "#FF6B5C", "name": "Coral", "source": CORAL_SOURCE, "confidence": 0.4},
        ],
        fonts=[{"family": "Archivo Black", "source": SAND_SOURCE, "confidence": 0.6}],
        theme_metadata={"shop_name": "Demo Apparel", "brand_slogan": "Wear the everyday", "theme_name": "Dawn"},
    )


def _gemini_colors() -> list[dict[str, Any]]:
    return [
        {
            "role_key": "primary",
            "base_hex": "#0e1a2b",
            "label": "Navy Ink",
            "usage_hint": "Headlines and anchors.",
            "agent_hint": "Dominant identity color.",
            "variants": [
                {"name": "Navy Soft", "hex": "#16263d", "usage_hint": "Muted panels"},
                {"name": "Broken", "hex": "not-a-hex", "usage_hint": ""},
                {"name": "Navy Soft Duplicate", "hex": "#16263D", "usage_hint": ""},
                {"name": "Same As Base", "hex": "#0E1A2B", "usage_hint": ""},
            ],
            "rationale": "Highest-confidence theme setting color.",
            "evidence_refs": [NAVY_SOURCE],
        },
        {
            "role_key": "secondary",
            "base_hex": "#F4EDE2",
            "label": "Sand",
            "usage_hint": "Backgrounds.",
            "agent_hint": "Support surfaces.",
            "variants": [],
            "rationale": "Dominant CSS background.",
            "evidence_refs": [SAND_SOURCE],
        },
        {
            "role_key": "tertiary",
            "base_hex": "#FF6B5C",
            "label": "Coral Pop",
            "usage_hint": "CTA buttons.",
            "agent_hint": "High-attention accents only.",
            "variants": [{"name": "Coral Hover", "hex": "#FF8478", "usage_hint": "CTA hover"}],
            "rationale": "Hero section accent.",
            "evidence_refs": [CORAL_SOURCE],
        },
        {
            "role_key": "primary",  # duplicate role: must be dropped, keeping the first
            "base_hex": "#000000",
            "label": "Late Duplicate",
            "usage_hint": "",
            "agent_hint": "",
            "variants": [],
            "rationale": "",
            "evidence_refs": [],
        },
    ]


def _patch_gemini(monkeypatch, result: Any) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    async def fake_generate(prompt, *, model, structured=None):
        captured["prompt"] = prompt
        captured["model"] = model
        captured["structured"] = structured
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(module.gemini_text, "generate", fake_generate)
    return captured


@pytest.mark.asyncio
async def test_success_three_roles_with_dedupe_invalid_hex_drop_and_evidence(monkeypatch):
    captured = _patch_gemini(monkeypatch, {"colors": _gemini_colors(), "summary": "Navy-led palette from theme evidence."})

    draft = await BrandRecommendationService().recommend_colors(brand=_brand(), snapshot=_snapshot())

    assert captured["model"] == module.gemini_text.FLASH_MODEL
    assert [color.role_key for color in draft.colors] == ["primary", "secondary", "tertiary"]

    primary = draft.colors[0]
    assert primary.base_hex == "#0E1A2B"  # normalized from lowercase
    assert primary.label == "Navy Ink"
    # Invalid hex dropped, duplicate hex deduped, base-hex variant deduped.
    assert [variant.hex for variant in primary.variants] == ["#16263D"]
    assert primary.variants[0].source == "gemini"
    assert primary.evidence_refs == [NAVY_SOURCE]
    assert primary.rationale == "Highest-confidence theme setting color."

    # Duplicate primary entry was dropped (first one kept).
    assert primary.label != "Late Duplicate"

    assert draft.colors[1].base_hex == "#F4EDE2"
    assert draft.colors[2].base_hex == "#FF6B5C"
    assert draft.summary == "Navy-led palette from theme evidence."
    assert draft.fonts == []  # reserved for Task 6
    assert draft.source_notes == ["theme_settings", "css", "section", "shop_metadata", "theme_metadata"]


@pytest.mark.asyncio
async def test_missing_roles_are_backfilled_from_existing_color_system(monkeypatch):
    colors = [item for item in _gemini_colors() if item["role_key"] != "secondary"]
    _patch_gemini(monkeypatch, {"colors": colors, "summary": ""})

    draft = await BrandRecommendationService().recommend_colors(brand=_brand(), snapshot=_snapshot())

    assert [color.role_key for color in draft.colors] == ["primary", "secondary", "tertiary"]
    secondary = draft.colors[1]
    assert secondary.base_hex == "#F5E8D0"  # existing approved secondary
    assert secondary.label == "Warm Paper"
    assert secondary.usage_hint == "Use for backgrounds."
    assert secondary.agent_hint == "Support the primary."
    assert [variant.hex for variant in secondary.variants] == ["#E3D2B4"]
    assert secondary.rationale == "kept from existing approved brand context"
    assert secondary.evidence_refs == []
    # Default summary when Gemini does not provide one.
    assert draft.summary == "Color role recommendations from 3 discovered colors"


@pytest.mark.asyncio
async def test_invalid_base_hex_role_falls_back_to_existing_role(monkeypatch):
    colors = _gemini_colors()
    colors[2]["base_hex"] = "coral-ish"  # tertiary becomes unusable
    _patch_gemini(monkeypatch, {"colors": colors})

    draft = await BrandRecommendationService().recommend_colors(brand=_brand(), snapshot=_snapshot())

    tertiary = draft.colors[2]
    assert tertiary.base_hex == "#FF6655"  # existing approved tertiary
    assert tertiary.rationale == "kept from existing approved brand context"


@pytest.mark.asyncio
async def test_evidence_refs_canonicalized_and_backfilled_from_snapshot_sources(monkeypatch):
    colors = _gemini_colors()[:3]
    colors[0]["evidence_refs"] = [NAVY_SOURCE.upper(), "gemini said so", ""]  # echo with wrong case + free text
    colors[1]["evidence_refs"] = []  # no echo: fall back to the discovered color source for #F4EDE2
    _patch_gemini(monkeypatch, {"colors": colors})

    draft = await BrandRecommendationService().recommend_colors(brand=_brand(), snapshot=_snapshot())

    assert draft.colors[0].evidence_refs == [NAVY_SOURCE, "gemini said so"]
    assert draft.colors[1].evidence_refs == [SAND_SOURCE]


@pytest.mark.asyncio
async def test_gemini_unavailable_raises_recommendation_unavailable(monkeypatch):
    _patch_gemini(monkeypatch, gemini_text.GeminiUnavailable("Gemini is unavailable: set GOOGLE_API_KEY"))

    with pytest.raises(BrandRecommendationUnavailable, match="Gemini is unavailable"):
        await BrandRecommendationService().recommend_colors(brand=_brand(), snapshot=_snapshot())


@pytest.mark.asyncio
async def test_unparseable_gemini_response_raises_recommendation_unavailable(monkeypatch):
    _patch_gemini(monkeypatch, "this is {not json")

    with pytest.raises(BrandRecommendationUnavailable, match="could not be parsed"):
        await BrandRecommendationService().recommend_colors(brand=_brand(), snapshot=_snapshot())


@pytest.mark.asyncio
async def test_empty_or_all_invalid_results_raise_recommendation_unavailable(monkeypatch):
    _patch_gemini(monkeypatch, {"colors": [], "summary": "nothing"})
    with pytest.raises(BrandRecommendationUnavailable, match="no valid color role"):
        await BrandRecommendationService().recommend_colors(brand=_brand(), snapshot=_snapshot())

    _patch_gemini(
        monkeypatch,
        {"colors": [{"role_key": "accent", "base_hex": "#123456"}, {"role_key": "primary", "base_hex": "nope"}]},
    )
    with pytest.raises(BrandRecommendationUnavailable, match="no valid color role"):
        await BrandRecommendationService().recommend_colors(brand=_brand(), snapshot=_snapshot())


@pytest.mark.asyncio
async def test_prompt_includes_existing_roles_discovered_colors_confidence_and_metadata(monkeypatch):
    captured = _patch_gemini(monkeypatch, {"colors": _gemini_colors()[:3]})

    await BrandRecommendationService().recommend_colors(brand=_brand(), snapshot=_snapshot())

    prompt = str(captured["prompt"])
    # Existing approved brand color system (so Gemini refines, not overwrites).
    assert "Hero Ink" in prompt
    assert "#112233" in prompt
    assert "Warm Paper" in prompt
    assert "refine, do not blindly overwrite" in prompt
    # Discovered colors with confidence + provenance, sorted highest confidence first.
    assert "#0E1A2B" in prompt
    assert "0.95" in prompt
    assert NAVY_SOURCE in prompt
    assert prompt.index("#0E1A2B") < prompt.index("#F4EDE2") < prompt.index("#FF6B5C")
    # Shop/theme metadata + assets summary.
    assert "Demo Apparel" in prompt
    assert "Wear the everyday" in prompt
    assert "Dawn" in prompt
    assert "https://cdn.shopify.com/logo.png" in prompt
    # Role semantics from ROLE_DEFAULTS and strict output instructions.
    assert "Main brand color for dominant identity moments" in prompt
    assert "Accent color for CTA" in prompt
    assert "strict JSON" in prompt
    assert "exactly one entry for each role_key" in prompt
