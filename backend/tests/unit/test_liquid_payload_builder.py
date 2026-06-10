from __future__ import annotations

import re

from app.agents.state import BannerAssets, Concept, Variant
from app.services.shopify.liquid_payload_builder import build_liquid_payload


def _section_style_attr(section: str) -> str:
    """The aijolot-banner section's style attribute value.

    The capture stops at the first double quote, so anything asserted inside the
    captured value is provably within an intact ``style="..."`` attribute.
    """

    match = re.search(r'<section class="aijolot-banner[^>]*? style="([^"]*)"', section)
    assert match, "section style attribute missing or broken"
    return match.group(1)


def _concept() -> Concept:
    return Concept(
        layout="hero-left",
        copy={"headline": "VIP Sale {{ bad }}", "subheadline": "Save more", "cta": "Shop deals"},
        palette_usage={"background": "Cream"},
        image_prompt="background",
        hierarchy_notes="",
    )


def test_liquid_payload_builder_returns_stable_controlled_payload() -> None:
    assets = BannerAssets(
        webp={1280: "https://cdn.example/banner.webp"},
        avif={},
        fallback_jpg={1280: "https://cdn.example/banner.jpg"},
        alt_text_suggestion="Alt",
        total_weight_kb_1280_webp=100,
        optimization_report={"avif_skipped": True},
    )
    payload = build_liquid_payload(
        _concept(),
        [Variant(customer_tag="VIP Customer", intent_delta="", copy_override={"headline": "VIP only"})],
        brand={"name": "Demo Brand", "shopify": {"default_placement": "home_hero"}},
        assets=assets,
    )
    again = build_liquid_payload(
        _concept(),
        [Variant(customer_tag="VIP Customer", intent_delta="", copy_override={"headline": "VIP only"})],
        brand={"name": "Demo Brand", "shopify": {"default_placement": "home_hero"}},
        assets=assets,
    )

    assert payload.as_dict() == again.as_dict()
    assert payload.section_filename.startswith("sections/aijolot-vip-sale-bad-")
    assert payload.snippet_filename == "snippets/aijolot-banner-block.liquid"
    assert "customer.tags" in payload.section
    assert "{{ headline }}" in payload.block_snippet
    assert payload.config["image"]["url"] == "https://cdn.example/banner.webp"
    assert payload.config["optimization_report"]["avif_skipped"] is True
    assert payload.config["color_system"] == {}


def test_liquid_payload_includes_color_system_and_role_css() -> None:
    concept = _concept().model_copy(update={"palette_usage": {"background": "Soft Cream", "text": "primary", "cta_background": "Action Amber", "cta_text": "#FFFFFF"}})
    brand = {
        "name": "Demo Brand",
        "shopify": {"default_placement": "home_hero"},
        "color_system": {
            "primary": {"key": "primary", "label": "Trust Blue", "hex": "#123456", "usage_hint": "anchor", "agent_hint": "identity", "variants": []},
            "secondary": {"key": "secondary", "label": "Warm Cream", "hex": "#F4F1EA", "usage_hint": "background", "agent_hint": "surface", "variants": [{"name": "Soft Cream", "hex": "#FFF6E6", "usage_hint": "background"}]},
            "tertiary": {"key": "tertiary", "label": "Sun Accent", "hex": "#FFAA00", "usage_hint": "cta", "agent_hint": "button", "variants": [{"name": "Action Amber", "hex": "#FF8800", "usage_hint": "cta"}]},
        },
    }

    payload = build_liquid_payload(concept, [], brand=brand)

    assert payload.config["color_system"]["secondary"]["variants"][0]["name"] == "Soft Cream"
    assert payload.config["role_css"] == {
        "background": "#FFF6E6",
        "text": "#123456",
        "cta_background": "#FF8800",
        "cta_text": "#FFFFFF",
    }
    assert "--aijolot-background:#FFF6E6;" in payload.section


def test_liquid_payload_includes_typography_config_and_font_css_vars() -> None:
    brand = {
        "name": "Demo Brand",
        "shopify": {"default_placement": "home_hero"},
        "typography": {
            "display": "Space Grotesk",
            "body": "Inter",
            "approved_fonts": [
                {
                    "family": "Space Grotesk",
                    "css_stack": '"Space Grotesk", Helvetica Neue, sans-serif',
                    "category": "sans",
                    "source": "gemini_suggested",
                    "status": "approved",
                    "recommended_roles": ["display", "headline"],
                    "rationale": "noise that must not reach the config",
                }
            ],
        },
    }

    payload = build_liquid_payload(_concept(), [], brand=brand)

    assert payload.config["typography"]["stacks"] == {
        "display": '"Space Grotesk", "Helvetica Neue", sans-serif',
        "body": "Inter, sans-serif",
    }
    assert payload.config["typography"]["approved_fonts"] == [
        {"family": "Space Grotesk", "category": "sans", "recommended_roles": ["display", "headline"]}
    ]
    assert payload.config["typography"]["legacy"] == {"display": "Space Grotesk", "body": "Inter"}

    style = _section_style_attr(payload.section)
    # Double quotes in the stack are converted to single quotes for the attribute,
    # so the family stays a valid CSS string and the attribute never breaks.
    assert "--aijolot-font-display:'Space Grotesk', 'Helvetica Neue', sans-serif;" in style
    assert "--aijolot-font-body:Inter, sans-serif;" in style
    assert '"' not in style
    assert "&quot;" not in style


def test_liquid_payload_typography_for_legacy_brand_uses_legacy_stacks() -> None:
    brand = {"name": "Demo Brand", "typography": {"display": "Archivo Black", "body": "Helvetica Neue, Arial, sans-serif"}}

    payload = build_liquid_payload(_concept(), [], brand=brand)

    assert payload.config["typography"]["stacks"] == {
        "display": '"Archivo Black", sans-serif',
        "body": '"Helvetica Neue", Arial, sans-serif',
    }
    assert payload.config["typography"]["approved_fonts"] == []
    assert payload.config["typography"]["legacy"]["body"] == "Helvetica Neue, Arial, sans-serif"

    style = _section_style_attr(payload.section)
    assert "--aijolot-font-display:'Archivo Black', sans-serif;" in style
    assert "--aijolot-font-body:'Helvetica Neue', Arial, sans-serif;" in style
    assert '"' not in style


def test_liquid_payload_without_typography_emits_empty_block_and_no_font_vars() -> None:
    payload = build_liquid_payload(_concept(), [], brand={"name": "Demo"})

    assert payload.config["typography"] == {}
    assert "--aijolot-font" not in payload.section


def test_cta_url_default_falls_back_to_catalog() -> None:
    payload = build_liquid_payload(_concept(), [], brand={"name": "Demo"})
    assert '"id":"cta_url","label":"CTA URL","default":"/collections/all"' in payload.section


def test_cta_url_uses_brief_destination_when_provided() -> None:
    payload = build_liquid_payload(_concept(), [], brand={"name": "Demo"}, cta_url="https://shop.example/landing")
    assert '"default":"https://shop.example/landing"' in payload.section


def test_liquid_payload_builder_does_not_accept_arbitrary_liquid_templates() -> None:
    payload = build_liquid_payload(
        _concept(),
        [Variant(customer_tag="default", intent_delta="", copy_override={"headline": "{{ product.title }}"})],
        brand={"name": "Demo"},
    )

    assert "{{ product.title }}" in payload.config["variants"][0]["headline"]
    assert "{{ product.title }}" not in payload.block_snippet
    assert "{{ product.title }}" not in payload.section
    assert "parse_json" not in payload.section
    assert "cta_url: section.settings.cta_url" in payload.section
    assert "matched_tag == 'default'" in payload.section
    assert "cta_url | default: routes.root_url | escape" in payload.block_snippet


def test_liquid_payload_builder_neutralizes_quote_and_tag_breakout() -> None:
    payload = build_liquid_payload(
        Concept(
            layout="hero",
            copy={"headline": "x' %}{{ product.title }}{% comment", "subheadline": "</script>", "cta": "Go"},
            palette_usage={},
            image_prompt="bg",
            hierarchy_notes="",
        ),
        [Variant(customer_tag="default", intent_delta="", copy_override={"headline": "x' %}{{ product.title }}{% comment"})],
        brand={"name": "Demo"},
    )

    assert "x' %}" not in payload.section
    assert "{{ product.title }}" not in payload.section
    assert "&#123;&#123; product.title &#125;&#125;" in payload.section


def test_liquid_payload_builder_keeps_normal_copy_single_escaped() -> None:
    payload = build_liquid_payload(
        Concept(
            layout="hero",
            copy={"headline": "Save & win", "subheadline": "Bob's shoes", "cta": "Shop <now>"},
            palette_usage={},
            image_prompt="bg",
            hierarchy_notes="",
        ),
        [],
        brand={"name": "Demo"},
    )

    assert "Save &amp; win" in payload.section
    assert "Bob&#x27;s shoes" in payload.section
    assert "Shop &lt;now&gt;" in payload.section
    assert "&amp;amp;" not in payload.section
