from __future__ import annotations

import pytest

from app.agents.tools import gemini_text
from app.schemas.brand import BrandContext
from app.schemas.palette_suggestions import PaletteSuggestionRouteRequest
from app.services.brands.palette_suggestions import PaletteSuggestionService, PaletteSuggestionUnavailable


def _brand(primary_hex: str = "#112233") -> BrandContext:
    return BrandContext.model_validate(
        {
            "id": "demo_brand",
            "name": "Demo Brand",
            "palette": [
                {"name": "Ink", "hex": primary_hex},
                {"name": "Paper", "hex": "#F5E8D0"},
                {"name": "CTA", "hex": "#FF6655"},
            ],
            "color_system": {
                "primary": {
                    "key": "primary",
                    "label": "Hero Ink",
                    "hex": primary_hex,
                    "usage_hint": "Use for hero headlines.",
                    "agent_hint": "Dominant visual anchor.",
                    "variants": [{"name": "Hero Ink Soft", "hex": "#223344", "usage_hint": "Muted hero panels."}],
                },
                "secondary": {
                    "key": "secondary",
                    "label": "Warm Paper",
                    "hex": "#F5E8D0",
                    "usage_hint": "Use for backgrounds.",
                    "agent_hint": "Support the primary.",
                    "variants": [],
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
            "voice": {"tone": ["Confident", "Warm"], "required_phrases": [], "prohibited_words": ["cheap"]},
            "image_style_directives": ["natural light", "premium product photography"],
            "shopify": {"store_domain": "demo.myshopify.com"},
            "notes": "Keep the brand editorial and clean.",
        }
    )


class FakeBrandService:
    def __init__(self, brand: BrandContext) -> None:
        self.brand = brand

    def get_brand(self, brand_id: str) -> BrandContext:
        assert brand_id == "demo_brand"
        return self.brand


@pytest.mark.asyncio
async def test_gemini_prompt_includes_context_role_colors_variants_and_intent(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_generate(prompt, *, model, structured=None):
        captured["prompt"] = prompt
        captured["model"] = model
        captured["structured"] = structured
        return {"suggestions": [{"name": "Fresh Green", "hex": "#33AA66", "usage_hint": "CTA accent", "rationale": "Keeps warmth."}]}

    from app.services.brands import palette_suggestions as module

    monkeypatch.setattr(module.gemini_text, "generate", fake_generate)
    response = await PaletteSuggestionService(FakeBrandService(_brand())).suggest(
        "demo_brand",
        PaletteSuggestionRouteRequest(role_key="primary", intent="summer sale hero"),
    )

    prompt = str(captured["prompt"])
    assert response.source == "gemini"
    assert captured["model"] == module.gemini_text.FLASH_MODEL
    assert "Demo Brand" in prompt
    assert "Hero Ink" in prompt
    assert "#112233" in prompt
    assert "#223344" in prompt
    assert "Confident" in prompt
    assert "natural light" in prompt
    assert "summer sale hero" in prompt


@pytest.mark.asyncio
async def test_suggestions_deduplicate_filter_invalid_and_existing_hexes(monkeypatch):
    async def fake_generate(prompt, *, model, structured=None):
        return {
            "suggestions": [
                {"name": "Bad", "hex": "not-a-hex", "usage_hint": "", "rationale": ""},
                {"name": "Existing Base", "hex": "#112233", "usage_hint": "", "rationale": ""},
                {"name": "Existing Variant", "hex": "#223344", "usage_hint": "", "rationale": ""},
                {"name": "Fresh", "hex": "#33aa66", "usage_hint": "Use on badges", "rationale": "Fresh contrast"},
                {"name": "Fresh Duplicate", "hex": "#33AA66", "usage_hint": "", "rationale": ""},
                {"name": "Gold", "hex": "#D9A441", "usage_hint": "Use on offers", "rationale": "Premium warmth"},
            ]
        }

    from app.services.brands import palette_suggestions as module

    monkeypatch.setattr(module.gemini_text, "generate", fake_generate)
    response = await PaletteSuggestionService(FakeBrandService(_brand())).suggest(
        "demo_brand",
        PaletteSuggestionRouteRequest(role_key="primary", count=3),
    )

    assert [item.hex for item in response.suggestions] == ["#33AA66", "#D9A441"]


@pytest.mark.asyncio
async def test_count_caps_returned_suggestions(monkeypatch):
    async def fake_generate(prompt, *, model, structured=None):
        return {
            "suggestions": [
                {"name": f"Color {i}", "hex": f"#{i:06X}", "usage_hint": "Use in banners", "rationale": "Fits."}
                for i in range(1, 12)
            ]
        }

    from app.services.brands import palette_suggestions as module

    monkeypatch.setattr(module.gemini_text, "generate", fake_generate)
    response = await PaletteSuggestionService(FakeBrandService(_brand())).suggest(
        "demo_brand",
        PaletteSuggestionRouteRequest(role_key="secondary", count=3),
    )

    assert len(response.suggestions) == 3


def test_invalid_role_key_validation_error():
    with pytest.raises(Exception):
        PaletteSuggestionRouteRequest(role_key="accent")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_missing_or_unavailable_gemini_raises_service_error(monkeypatch):
    async def fake_generate(prompt, *, model, structured=None):
        raise gemini_text.GeminiUnavailable("Gemini is unavailable: set GOOGLE_API_KEY")

    from app.services.brands import palette_suggestions as module

    monkeypatch.setattr(module.gemini_text, "generate", fake_generate)
    with pytest.raises(PaletteSuggestionUnavailable, match="Gemini is unavailable"):
        await PaletteSuggestionService(FakeBrandService(_brand())).suggest(
            "demo_brand",
            PaletteSuggestionRouteRequest(role_key="primary"),
        )


@pytest.mark.asyncio
async def test_draft_brand_context_overrides_persisted_brand(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_generate(prompt, *, model, structured=None):
        captured["prompt"] = prompt
        return {"suggestions": [{"name": "Draft Blue", "hex": "#2F80ED", "usage_hint": "Use for draft hero", "rationale": "Matches draft."}]}

    from app.services.brands import palette_suggestions as module

    monkeypatch.setattr(module.gemini_text, "generate", fake_generate)
    draft = _brand(primary_hex="#445566")
    draft.name = "Unsaved Draft Brand"
    response = await PaletteSuggestionService(FakeBrandService(_brand(primary_hex="#112233"))).suggest(
        "demo_brand",
        PaletteSuggestionRouteRequest(role_key="primary", draft_brand_context=draft),
    )

    assert response.base_hex == "#445566"
    assert "Unsaved Draft Brand" in captured["prompt"]
    assert "#445566" in captured["prompt"]
    assert "#112233" not in captured["prompt"]


@pytest.mark.asyncio
async def test_no_valid_suggestions_raises_unavailable(monkeypatch):
    async def fake_generate(prompt, *, model, structured=None):
        return {"suggestions": [{"name": "Bad", "hex": "#112233", "usage_hint": "", "rationale": ""}]}

    from app.services.brands import palette_suggestions as module

    monkeypatch.setattr(module.gemini_text, "generate", fake_generate)
    with pytest.raises(PaletteSuggestionUnavailable, match="no valid"):
        await PaletteSuggestionService(FakeBrandService(_brand())).suggest(
            "demo_brand",
            PaletteSuggestionRouteRequest(role_key="primary"),
        )
