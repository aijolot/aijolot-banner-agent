from __future__ import annotations

from app.agents.state import BannerAssets, Concept, Variant
from app.services.shopify.liquid_payload_builder import build_liquid_payload


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
