from __future__ import annotations

import asyncio
import importlib.util
import re
from pathlib import Path

import pytest

from app.agents.state import Campaign, Concept
from app.schemas.art_direction import ArtDirectionUpsert
from app.schemas.catalog import CatalogSnapshotItem, CatalogSnapshotResponse
from app.schemas.placements import PlacementValidateRequest


SKILL_ROOT = Path(__file__).resolve().parents[3] / "app" / "agents" / "skills"


def _load_skill(skill_id: str):
    path = SKILL_ROOT / skill_id / "impl.py"
    spec = importlib.util.spec_from_file_location(f"test_{skill_id.replace('-', '_')}_impl", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _campaign() -> Campaign:
    return Campaign(
        goal="Black Friday 40% off running shoes",
        audience="VIP women runners looking for premium deals",
        cta="Shop the deal",
        tone="Confident",
        urgency="high",
        placement="Home · Hero",
    )


def _brand_dict():
    return {
        "id": "aijolot_demo",
        "name": "Aijolot Demo",
        "palette": [
            {"name": "Logo Blue", "hex": "#123456"},
            {"name": "Text White", "hex": "#F4F1EA"},
            {"name": "Sun", "hex": "#FFAA00"},
        ],
        "voice": {
            "tone": ["confident", "warm"],
            "required_phrases": ["Move brighter"],
            "prohibited_words": ["cheap"],
        },
        "image_style_directives": ["natural light", "premium minimal set"],
        "shopify": {"store_domain": "demo.myshopify.com", "default_placement": "hero"},
        "notes": "Athletic lifestyle brand.",
    }


def test_end_to_end_context_to_concept_to_image_prompt_is_deterministic():
    brand_skill = _load_skill("brand-context-load")
    personalization_skill = _load_skill("user-personalization")
    practices_skill = _load_skill("best-practices-retrieve")
    concept_skill = _load_skill("banner-concept-draft")
    image_skill = _load_skill("image-prompt-refine")

    brand = asyncio.run(brand_skill.run(brand_context=_brand_dict()))
    assert brand.id == "aijolot_demo"
    assert brand.palette[0].hex == "#123456"
    assert brand.voice.required_phrases == ["Move brighter"]

    campaign = _campaign()
    variants = asyncio.run(personalization_skill.run(campaign, customer_tags=["VIP", "deal seeker"]))
    assert [variant.customer_tag for variant in variants][:3] == ["default", "vip", "deal_seeker"]
    assert variants[0].copy_override["urgency"] == "Act now"

    practices_1 = asyncio.run(practices_skill.run(campaign, brand, top_k=4))
    practices_2 = asyncio.run(practices_skill.run(campaign, brand, top_k=4))
    assert practices_1 == practices_2
    assert len(practices_1) == 4
    assert {doc["source"] for doc in practices_1} == {"static"}
    assert any(doc["kind"] == "best_practice" for doc in practices_1)

    catalog = CatalogSnapshotResponse(
        id="snap_1",
        campaign_id="camp_1",
        query_summary="running shoes on sale",
        items=[CatalogSnapshotItem(title="Cloud Runner", price=120.0, sale_price=72.0, tags=["running"])],
        item_count=1,
    )
    placement = PlacementValidateRequest(
        store_id="11111111-1111-1111-1111-111111111111",
        placement_type_key="home_hero",
        mode="new_section",
        target_type="home",
    ).to_normalized()
    art = ArtDirectionUpsert(background_mode="hero", fold_percentage=60, layout_hints={"copy_side": "left"})

    concept = asyncio.run(concept_skill.run(
        campaign=campaign,
        brand_context=brand,
        variants=variants,
        best_practices=practices_1,
        catalog_context=catalog,
        placement_context=placement,
        art_direction=art,
    ))
    assert isinstance(concept, Concept)
    assert concept.copy["headline"]
    assert "Move brighter" in concept.copy["headline"]
    assert concept.copy["cta"] == "Shop the deal"
    forbidden_prompt_terms = ("text", "words", "letters", "signage", "caption", "captions", "headline", "headlines", "logo", "logos", "ui", "faces", "buttons", "modals", "screens")
    assert all(term not in concept.image_prompt.lower() for term in forbidden_prompt_terms)
    assert "Primary" in concept.image_prompt
    assert "#123456" not in concept.image_prompt

    prompt = asyncio.run(image_skill.run(concept, brand_context=brand, catalog_context=catalog, art_direction=art))
    assert prompt == asyncio.run(image_skill.run(concept, brand_context=brand, catalog_context=catalog, art_direction=art))
    assert "ecommerce banner background" in prompt
    assert "Cloud Runner" in prompt
    # Hex codes must never reach the image prompt (they render as on-canvas color
    # swatches); the brand palette is cued without hex and enforced in HTML/Liquid.
    assert "#123456" not in prompt
    assert "16:9" in prompt
    assert "\n" not in prompt
    assert 60 <= len(re.findall(r"\b\w+\b", prompt)) <= 120
    forbidden_prompt_terms = ("text", "words", "letters", "signage", "caption", "captions", "headline", "headlines", "logo", "logos", "ui", "faces", "buttons", "modals", "screens")
    assert all(term not in prompt.lower() for term in forbidden_prompt_terms)


def test_kg_static_retrieval_filters_and_indexes_without_external_calls():
    kg = __import__("app.agents.tools.kg", fromlist=["retrieve", "index"])

    docs = asyncio.run(kg.retrieve("cta urgency hero", kinds=["best_practice"], brand_id="demo", top_k=2))
    assert len(docs) == 2
    assert all(doc["kind"] == "best_practice" for doc in docs)
    assert all(doc["id"] for doc in docs)
    assert docs == asyncio.run(kg.retrieve("cta urgency hero", kinds=["best_practice"], brand_id="demo", top_k=2))

    doc_id = asyncio.run(kg.index({"kind": "best_practice", "title": "Static", "body": "No network"}))
    assert doc_id == asyncio.run(kg.index({"kind": "best_practice", "title": "Static", "body": "No network"}))
    assert asyncio.run(kg.retrieve("zzzxqv blorptastic unrelated", kinds=["best_practice"], top_k=5)) == []


def test_image_prompt_sanitizes_text_logo_face_requests():
    image_skill = _load_skill("image-prompt-refine")
    prompt = asyncio.run(image_skill.run(
        "Product photo with text area, text overlay, logo, faces, UI, no signage, signage, captions, caption, headlines, headline, letters, buttons, modals, and screens",
        image_style_directives="studio logo wall",
        brand_context={"image_style_directives": ["premium logo wall", "UI inspired"]},
    ))
    lowered = prompt.lower()
    assert "\n" not in prompt
    assert 60 <= len(re.findall(r"\b\w+\b", prompt)) <= 120
    assert "16:9" in prompt
    forbidden_prompt_terms = ("text", "words", "letters", "signage", "caption", "captions", "headline", "headlines", "logo", "logos", "ui", "faces", "buttons", "modals", "screens")
    assert all(term not in lowered for term in forbidden_prompt_terms)
    assert "text overlay" not in lowered


def test_brand_context_loads_markdown_by_brand_id_and_preserves_string_fields():
    brand_skill = _load_skill("brand-context-load")

    brand = asyncio.run(brand_skill.run("demo_apparel"))
    assert brand.id == "demo_apparel"
    assert brand.name == "Demo Apparel"
    assert brand.palette[0].name == "Ink"

    normalized = asyncio.run(brand_skill.run(brand_context={
        "id": "string_voice",
        "name": "String Voice",
        "palette": [{"name": "Ink", "hex": "#111111"}],
        "voice": {"tone": "Bold", "prohibited_words": "cheap", "required_phrases": "Always on"},
        "image_style_directives": "studio light",
        "shopify": {"store_domain": "demo.myshopify.com"},
    }))
    assert normalized.voice.tone == ["Bold"]
    assert normalized.voice.prohibited_words == ["cheap"]
    assert normalized.voice.required_phrases == ["Always on"]
    assert normalized.image_style_directives == ["studio light"]


def test_concept_respects_prohibited_words_palette_tokens_and_required_phrase_truncation():
    brand_skill = _load_skill("brand-context-load")
    concept_skill = _load_skill("banner-concept-draft")
    brand_data = _brand_dict()
    brand_data["voice"]["prohibited_words"] = ["cheap", "luxury"]
    brand_data["voice"]["required_phrases"] = ["Move brighter"]
    brand = asyncio.run(brand_skill.run(brand_context=brand_data))

    concept = asyncio.run(concept_skill.run(
        campaign=Campaign(
            goal="Cheap luxury running collection with an exceptionally long benefit promise for shoppers",
            audience="cheap luxury buyers",
            cta="Shop cheap now",
            tone="Cheap Luxury",
            urgency="medium",
            placement="hero",
        ),
        brand_context=brand,
        catalog_context=CatalogSnapshotResponse(
            id="unsafe_snap",
            campaign_id="camp_unsafe",
            items=[CatalogSnapshotItem(title="Logo Face UI Text Hoodie")],
            item_count=1,
        ),
    ))

    copy_blob = " ".join(str(value) for value in concept.copy.values()).lower()
    assert "cheap" not in copy_blob
    assert "luxury" not in copy_blob
    assert "Move brighter" in concept.copy["headline"]
    assert len(concept.copy["headline"]) <= 58
    assert concept.palette_usage == {
        "background": "Secondary",
        "text": "Primary",
        "cta_background": "Tertiary / Accent",
        "cta_text": "Secondary",
    }
    forbidden_prompt_terms = ("text", "words", "letters", "signage", "caption", "captions", "headline", "headlines", "logo", "logos", "ui", "faces", "buttons", "modals", "screens")
    assert all(term not in concept.image_prompt.lower() for term in forbidden_prompt_terms)


def test_concept_and_image_prompt_use_color_system_variants() -> None:
    brand_skill = _load_skill("brand-context-load")
    concept_skill = _load_skill("banner-concept-draft")
    image_skill = _load_skill("image-prompt-refine")
    brand_data = _brand_dict()
    brand_data["color_system"] = {
        "primary": {
            "key": "primary",
            "label": "Trust Blue",
            "hex": "#123456",
            "usage_hint": "Main identity and visual anchor",
            "agent_hint": "Use for primary anchor moments",
            "variants": [{"name": "Readable Navy", "hex": "#0B1F33", "usage_hint": "approved text foreground"}],
        },
        "secondary": {
            "key": "secondary",
            "label": "Warm Cream",
            "hex": "#F4F1EA",
            "usage_hint": "Support background fields",
            "agent_hint": "Use for background surfaces",
            "variants": [{"name": "Soft Cream", "hex": "#FFF6E6", "usage_hint": "approved background surface"}],
        },
        "tertiary": {
            "key": "tertiary",
            "label": "Sun Accent",
            "hex": "#FFAA00",
            "usage_hint": "CTA and accent color",
            "agent_hint": "Use for CTA buttons and highlights",
            "variants": [{"name": "Action Amber", "hex": "#FF8800", "usage_hint": "approved CTA button accent"}],
        },
    }
    brand = asyncio.run(brand_skill.run(brand_context=brand_data))

    concept = asyncio.run(concept_skill.run(campaign=_campaign(), brand_context=brand))

    assert concept.palette_usage["background"] == "Soft Cream"
    assert concept.palette_usage["cta_background"] == "Action Amber"
    assert concept.palette_usage["text"] == "Readable Navy"

    prompt = asyncio.run(image_skill.run(concept, brand_context=brand))
    # Color ROLE guidance reaches the image prompt by label + usage hint, but the
    # hex codes are stripped (they would render as literal swatches on the canvas).
    assert "Trust Blue" in prompt
    assert "Action Amber" in prompt
    assert "Use for CTA" in prompt
    assert "#123456" not in prompt
    assert "#FF8800" not in prompt


def test_concept_includes_typography_guidance_for_approved_fonts() -> None:
    brand_skill = _load_skill("brand-context-load")
    concept_skill = _load_skill("banner-concept-draft")
    image_skill = _load_skill("image-prompt-refine")
    brand_data = _brand_dict()
    brand_data["typography"] = {
        "display": "Space Grotesk",
        "body": "Inter",
        "approved_fonts": [
            {
                "family": "Space Grotesk",
                "css_stack": '"Space Grotesk", sans-serif',
                "category": "sans",
                "source": "gemini_suggested",
                "status": "approved",
                "recommended_roles": ["display"],
            }
        ],
    }
    brand = asyncio.run(brand_skill.run(brand_context=brand_data))

    concept = asyncio.run(concept_skill.run(campaign=_campaign(), brand_context=brand))

    assert "Typography: display: Space Grotesk (approved, sans), body: Inter (legacy)" in concept.hierarchy_notes
    # Image pixels stay text-free: only the display CATEGORY vibe enters the prompt.
    assert "geometric sans-serif aesthetic" in concept.image_prompt
    assert "Space Grotesk" not in concept.image_prompt
    assert "Inter" not in concept.image_prompt
    forbidden_prompt_terms = ("text", "words", "letters", "signage", "caption", "captions", "headline", "headlines", "logo", "logos", "ui", "faces", "buttons", "modals", "screens")
    assert all(term not in concept.image_prompt.lower() for term in forbidden_prompt_terms)

    prompt = asyncio.run(image_skill.run(concept, brand_context=brand))
    assert "Match a geometric sans-serif aesthetic in props and composition." in prompt
    assert "Space Grotesk" not in prompt
    assert all(term not in prompt.lower() for term in forbidden_prompt_terms)


def test_concept_and_image_prompt_unchanged_without_typography() -> None:
    brand_skill = _load_skill("brand-context-load")
    concept_skill = _load_skill("banner-concept-draft")
    image_skill = _load_skill("image-prompt-refine")
    brand_data = _brand_dict()
    # Legacy payloads may carry blank typography strings; no fonts must resolve.
    brand_data["typography"] = {"display": "", "body": ""}
    brand = asyncio.run(brand_skill.run(brand_context=brand_data))

    concept = asyncio.run(concept_skill.run(campaign=_campaign(), brand_context=brand))

    assert "Typography:" not in concept.hierarchy_notes
    assert "aesthetic" not in concept.image_prompt

    prompt = asyncio.run(image_skill.run(concept, brand_context=brand))
    assert "Match a" not in prompt

    # Dict-shaped brand without any typography keeps today's behavior too.
    dict_prompt = asyncio.run(image_skill.run(concept, brand_context={"image_style_directives": ["natural light"]}))
    assert "Match a" not in dict_prompt


def test_personalization_always_includes_default_and_caps_at_four():
    personalization_skill = _load_skill("user-personalization")
    variants = asyncio.run(personalization_skill.run(
        _campaign(),
        customer_tags=["VIP", "deal seeker", "gift buyer", "new customer", "category browser"],
        max_variants=99,
    ))
    assert [variant.customer_tag for variant in variants] == ["default", "vip", "deal_seeker", "gift_buyer"]

    one_variant = asyncio.run(personalization_skill.run(_campaign(), customer_tags=["VIP"], max_variants=0))
    assert [variant.customer_tag for variant in one_variant] == ["default"]


def test_kg_document_repository_validates_brand_id_and_embedding():
    repo_module = __import__("app.db.repositories.kg_documents", fromlist=["KGDocumentRepository"])
    repo = repo_module.KGDocumentRepository(client=None)

    with pytest.raises(ValueError):
        repo.list(brand_id="demo,brand_id.not.is.null")

    with pytest.raises(ValueError):
        repo.insert(data={"kind": "best_practice", "title": "Bad", "body": "Missing embedding"})

    with pytest.raises(ValueError):
        repo.insert(data={"kind": "best_practice", "title": "Bad", "body": "Bad embedding", "embedding": [0.1]})

    with pytest.raises(ValueError):
        repo.insert(data={"kind": "best_practice", "title": "Bad", "body": "Unsafe brand", "brand_id": "demo,brand_id.not.is.null", "embedding": [0.0] * 768})

    with pytest.raises(ValueError):
        repo.insert(data={"kind": "best_practice", "title": "Bad", "body": "Bad embedding values", "embedding": ["0"] * 768})

    with pytest.raises(ValueError):
        repo.insert(data={"kind": "best_practice", "title": "Bad", "body": "Bool embedding values", "embedding": [True] * 768})

    with pytest.raises(ValueError):
        repo.insert(data={"kind": "best_practice", "title": "Bad", "body": "NaN embedding values", "embedding": [float("nan")] * 768})
