"""Unit tests for the Gemini-backed font suggestion service (Task 6).

Mirrors ``test_palette_suggestions.py``: ``gemini_text.generate`` is monkeypatched on
the service module, no network, no real Gemini. The key difference from the color
services: Gemini-down does NOT raise - it returns an explicitly labeled non-AI
fallback (curated seeds + deterministic discoveries) with ``suggestions`` empty.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.agents.tools import gemini_text
from app.schemas.brand import BrandContext
from app.schemas.brand_discovery import BrandDiscoverySnapshot
from app.services.brands import font_suggestions as module
from app.services.brands.brand_service import BrandNotFound
from app.services.brands.font_discovery import SYSTEM_SEED_FONTS
from app.services.brands.font_suggestions import (
    FontSuggestionRouteRequest,
    FontSuggestionService,
)

THEME_SOURCE = "theme_settings:config/settings_data.json"
CSS_SOURCE = "css:assets/base.css"


def _brand(**typography_overrides: Any) -> BrandContext:
    typography = {
        "display": "Archivo Black",
        "body": "Inter",
        "approved_fonts": [
            {
                "family": "Archivo Black",
                "css_stack": "'Archivo Black', sans-serif",
                "category": "display",
                "source": "shopify_theme",
                "status": "approved",
                "recommended_roles": ["display"],
                "rationale": "Storefront hero already uses it.",
                "evidence_refs": [THEME_SOURCE],
            }
        ],
        "discarded_fonts": [
            {
                "family": "Papyrus",
                "css_stack": "Papyrus, fantasy",
                "category": "handwritten",
                "source": "gemini_suggested",
                "status": "discarded",
                "rationale": "Off-brand.",
            }
        ],
        **typography_overrides,
    }
    return BrandContext.model_validate(
        {
            "id": "demo_brand",
            "name": "Demo Apparel",
            "palette": [{"name": "Ink", "hex": "#112233"}],
            "typography": typography,
            "voice": {"tone": ["Confident", "Warm"], "required_phrases": [], "prohibited_words": []},
            "image_style_directives": ["natural light", "premium product photography"],
            "shopify": {"store_domain": "demo-apparel.myshopify.com"},
        }
    )


def _snapshot_dict() -> dict[str, Any]:
    return BrandDiscoverySnapshot(
        id="disc_abc123def456",
        brand_id="demo_brand",
        shop_domain="demo-apparel.myshopify.com",
        status="succeeded",
        discovered_at=datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc),
        fonts=[
            {"family": "Assistant", "source": THEME_SOURCE, "confidence": 0.9},
            {"family": "Archivo Black", "source": CSS_SOURCE, "css_stack": "'Archivo Black', sans-serif", "confidence": 0.55},
        ],
    ).model_dump(mode="json")


class FakeBrandService:
    """Just the two methods FontSuggestionService consumes."""

    def __init__(self, brand: BrandContext, snapshot: dict[str, Any] | None = None) -> None:
        self.brand = brand
        self.snapshot = snapshot
        self.snapshot_requests: list[str] = []

    def get_brand(self, brand_id: str) -> BrandContext:
        if brand_id != "demo_brand":
            raise BrandNotFound(brand_id)
        return self.brand

    def get_discovery_snapshot(self, brand_id: str) -> dict[str, Any] | None:
        self.snapshot_requests.append(brand_id)
        return self.snapshot


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


def _gemini_suggestions() -> dict[str, Any]:
    return {
        "suggestions": [
            {
                "family": "Space Grotesk",
                "css_stack": "",  # missing stack -> deterministically built
                "category": "grotesque-display",  # invalid category -> heuristic
                "recommended_roles": ["display", "Headline", "hero", "display"],  # junk filtered, deduped
                "rationale": "Pairs with Inter for body copy.",
            },
            {"family": "Papyrus", "css_stack": "Papyrus, fantasy", "category": "handwritten", "recommended_roles": ["accent"], "rationale": "x"},  # discarded
            {"family": "assistant", "css_stack": "Assistant, sans-serif", "category": "sans", "recommended_roles": ["body"], "rationale": "x"},  # discovered dup
            {"family": "Archivo Black", "css_stack": "'Archivo Black', sans-serif", "category": "display", "recommended_roles": ["display"], "rationale": "x"},  # approved dup
            {"family": "Bad<Font>", "css_stack": "Bad, sans-serif", "category": "sans", "recommended_roles": ["body"], "rationale": "x"},  # unsafe family
            {"family": "", "css_stack": "", "category": None, "recommended_roles": None, "rationale": None},  # tolerated junk
            {"family": "Lora", "css_stack": "Lora, Georgia, serif", "category": "serif", "recommended_roles": ["body"], "rationale": "Editorial pairing."},
            {"family": "SPACE GROTESK", "css_stack": "", "category": "sans", "recommended_roles": [], "rationale": "dup of an earlier suggestion"},
            {"family": "Poppins", "css_stack": "Poppins, url(evil), sans-serif", "category": "sans", "recommended_roles": ["headline"], "rationale": "Friendly retail."},  # bad stack -> rebuilt
            {"family": "Oswald", "css_stack": "Oswald, sans-serif", "category": "display", "recommended_roles": ["display"], "rationale": "Beyond count."},
        ]
    }


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_returns_gemini_suggestions_with_dedupe_validation_and_count(monkeypatch):
    captured = _patch_gemini(monkeypatch, _gemini_suggestions())
    service = FontSuggestionService(FakeBrandService(_brand(), _snapshot_dict()))

    response = await service.suggest("demo_brand", FontSuggestionRouteRequest(count=3))

    assert captured["model"] == module.gemini_text.FLASH_MODEL
    assert response.source == "gemini"
    assert response.ai_available is True
    assert response.message

    # Count respected, blocked families (discarded/approved/discovered) and dups dropped.
    assert [font.family for font in response.suggestions] == ["Space Grotesk", "Lora", "Poppins"]
    assert all(font.source == "gemini_suggested" for font in response.suggestions)
    assert all(font.status == "candidate" for font in response.suggestions)

    grotesk = response.suggestions[0]
    assert grotesk.css_stack == '"Space Grotesk", sans-serif'  # built when missing
    assert grotesk.category == "sans"  # heuristic replaces the invalid category
    assert grotesk.recommended_roles == ["display", "headline"]  # junk filtered, case-folded, deduped
    assert grotesk.rationale == "Pairs with Inter for body copy."

    assert response.suggestions[1].css_stack == "Lora, Georgia, serif"  # valid stack kept
    assert response.suggestions[2].css_stack == "Poppins, sans-serif"  # unsafe stack rebuilt, family kept

    # Discovered evidence rides along, deterministically labeled.
    assert [font.family for font in response.discovered] == ["Assistant", "Archivo Black"]
    assert {font.source for font in response.discovered} == {"shopify_theme", "storefront_css"}

    # Seeds keep their non-AI label and never duplicate suggestions or settled families.
    seed_families = {font.family for font in response.seeds}
    assert "Inter" in seed_families
    assert seed_families.isdisjoint({"Space Grotesk", "Lora", "Poppins"})
    assert all(font.source == "system_seed" for font in response.seeds)


@pytest.mark.asyncio
async def test_never_suggests_discarded_or_approved_families(monkeypatch):
    _patch_gemini(monkeypatch, _gemini_suggestions())
    service = FontSuggestionService(FakeBrandService(_brand(), _snapshot_dict()))

    response = await service.suggest("demo_brand", FontSuggestionRouteRequest(count=16))

    suggested = {font.family.lower() for font in response.suggestions}
    assert "papyrus" not in suggested  # discarded
    assert "archivo black" not in suggested  # approved
    assert "assistant" not in suggested  # discovered
    assert "bad<font>" not in suggested  # whitelist
    seeded = {font.family.lower() for font in response.seeds}
    assert "papyrus" not in seeded and "archivo black" not in seeded


@pytest.mark.asyncio
async def test_prompt_includes_context_discarded_discovered_seeds_roles_and_intent(monkeypatch):
    captured = _patch_gemini(monkeypatch, _gemini_suggestions())
    service = FontSuggestionService(FakeBrandService(_brand(), _snapshot_dict()))

    await service.suggest("demo_brand", FontSuggestionRouteRequest(count=5, intent="summer drop hero"))

    prompt = str(captured["prompt"])
    assert captured["structured"] is module._GeminiFontSuggestionPayload
    assert "Demo Apparel" in prompt
    assert "Confident" in prompt  # voice tone
    assert "natural light" in prompt  # image directives
    assert "summer drop hero" in prompt  # intent
    assert "exactly 5" in prompt  # count
    # Current typography incl. approved + discarded families (never re-suggest discarded).
    assert "Archivo Black" in prompt
    assert "Papyrus" in prompt
    assert "NEVER suggest a font family the user already discarded" in prompt
    # Discovered families with provenance.
    assert "Assistant" in prompt
    assert THEME_SOURCE in prompt
    # Seed families as the allowed safe pool.
    assert "Allowed safe pool" in prompt
    assert "JetBrains Mono" in prompt
    # Role semantics for all five roles.
    for role in ("display", "headline", "body", "accent", "caption"):
        assert role in prompt
    assert "strict JSON" in prompt


@pytest.mark.asyncio
async def test_draft_brand_context_overrides_persisted_typography(monkeypatch):
    captured = _patch_gemini(monkeypatch, _gemini_suggestions())
    draft = _brand(
        discarded_fonts=[
            {
                "family": "Comic Sans MS",
                "css_stack": "'Comic Sans MS', cursive",
                "category": "handwritten",
                "source": "manual",
                "status": "discarded",
            }
        ]
    )
    draft.name = "Unsaved Draft Brand"
    service = FontSuggestionService(FakeBrandService(_brand(), _snapshot_dict()))

    response = await service.suggest(
        "demo_brand", FontSuggestionRouteRequest(count=4, draft_brand_context=draft)
    )

    prompt = str(captured["prompt"])
    assert "Unsaved Draft Brand" in prompt
    assert "Comic Sans MS" in prompt  # draft's discarded list reaches the prompt
    assert "Papyrus" not in prompt  # persisted discard list replaced by the draft
    # Papyrus is only blocked through the draft context, so it may appear again,
    # while the draft's own discarded family stays blocked.
    assert "papyrus" in {font.family.lower() for font in response.suggestions}


@pytest.mark.asyncio
async def test_unknown_brand_propagates_brand_not_found(monkeypatch):
    _patch_gemini(monkeypatch, _gemini_suggestions())
    service = FontSuggestionService(FakeBrandService(_brand(), None))

    with pytest.raises(BrandNotFound):
        await service.suggest("nope", FontSuggestionRouteRequest())


@pytest.mark.asyncio
async def test_include_flags_control_discovered_and_seeds(monkeypatch):
    _patch_gemini(monkeypatch, _gemini_suggestions())
    fake = FakeBrandService(_brand(), _snapshot_dict())
    service = FontSuggestionService(fake)

    response = await service.suggest(
        "demo_brand",
        FontSuggestionRouteRequest(count=3, include_discovered=False, include_seeds=False),
    )

    assert fake.snapshot_requests == []  # snapshot not even consulted
    assert response.discovered == []
    assert response.seeds == []
    # Without the snapshot, discovered families are unknown and cannot be deduped
    # against; approved/discarded dedupe still applies.
    assert [font.family for font in response.suggestions] == ["Space Grotesk", "assistant", "Lora"]
    assert "archivo black" not in {font.family.lower() for font in response.suggestions}


@pytest.mark.asyncio
async def test_missing_snapshot_means_no_discovered_candidates(monkeypatch):
    _patch_gemini(monkeypatch, _gemini_suggestions())
    service = FontSuggestionService(FakeBrandService(_brand(), None))  # markdown/demo mode

    response = await service.suggest("demo_brand", FontSuggestionRouteRequest(count=3))

    assert response.discovered == []
    assert response.source == "gemini"


def test_request_count_bounds_are_validated():
    with pytest.raises(Exception):
        FontSuggestionRouteRequest(count=2)
    with pytest.raises(Exception):
        FontSuggestionRouteRequest(count=17)
    assert FontSuggestionRouteRequest().count == 8


# ---------------------------------------------------------------------------
# Fallback paths (Gemini down/unusable -> labeled non-AI response, no exception)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_unavailable_returns_labeled_deterministic_fallback(monkeypatch):
    _patch_gemini(monkeypatch, gemini_text.GeminiUnavailable("Gemini is unavailable: set GOOGLE_API_KEY"))
    service = FontSuggestionService(FakeBrandService(_brand(), _snapshot_dict()))

    response = await service.suggest("demo_brand", FontSuggestionRouteRequest())

    assert response.source == "deterministic_fallback"
    assert response.ai_available is False
    assert response.suggestions == []  # never fake AI output
    assert "Gemini is unavailable" in response.message
    assert "non-AI" in response.message
    # Deterministic buckets stay available so the user is not blocked.
    assert [font.family for font in response.discovered] == ["Assistant", "Archivo Black"]
    assert response.seeds
    assert all(font.source == "system_seed" for font in response.seeds)
    seeded = {font.family.lower() for font in response.seeds}
    assert "papyrus" not in seeded and "archivo black" not in seeded


@pytest.mark.asyncio
async def test_unparseable_gemini_response_falls_back(monkeypatch):
    _patch_gemini(monkeypatch, "this is {not json")
    service = FontSuggestionService(FakeBrandService(_brand(), _snapshot_dict()))

    response = await service.suggest("demo_brand", FontSuggestionRouteRequest())

    assert response.source == "deterministic_fallback"
    assert response.ai_available is False
    assert response.suggestions == []
    assert "could not be parsed" in response.message


@pytest.mark.asyncio
async def test_empty_or_fully_filtered_gemini_response_falls_back(monkeypatch):
    service = FontSuggestionService(FakeBrandService(_brand(), _snapshot_dict()))

    _patch_gemini(monkeypatch, {"suggestions": []})
    empty = await service.suggest("demo_brand", FontSuggestionRouteRequest())
    assert empty.source == "deterministic_fallback"
    assert empty.ai_available is False
    assert "no usable font suggestions" in empty.message

    _patch_gemini(monkeypatch, {"suggestions": [{"family": "Papyrus"}, {"family": "Bad<Font>"}]})
    filtered = await service.suggest("demo_brand", FontSuggestionRouteRequest())
    assert filtered.source == "deterministic_fallback"
    assert filtered.suggestions == []


@pytest.mark.asyncio
async def test_unexpected_gemini_crash_falls_back_instead_of_raising(monkeypatch):
    _patch_gemini(monkeypatch, RuntimeError("kaboom"))
    service = FontSuggestionService(FakeBrandService(_brand(), _snapshot_dict()))

    response = await service.suggest("demo_brand", FontSuggestionRouteRequest(include_seeds=False))

    assert response.source == "deterministic_fallback"
    assert response.ai_available is False
    assert response.seeds == []  # include_seeds=False respected even in fallback
    assert "RuntimeError" in response.message
    assert "kaboom" not in response.message  # no raw exception text leaked


def test_seed_pool_reference_is_not_mutated_by_responses():
    # The service hands out copies; mutating a response seed must not poison the pool.
    original = [seed.model_dump() for seed in SYSTEM_SEED_FONTS]
    seeds = FontSuggestionService._seeds(FontSuggestionRouteRequest(), exclude=set())
    seeds[0].rationale = "mutated"
    seeds[0].recommended_roles.append("caption")
    assert [seed.model_dump() for seed in SYSTEM_SEED_FONTS] == original
