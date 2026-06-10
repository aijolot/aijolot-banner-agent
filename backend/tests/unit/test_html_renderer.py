from __future__ import annotations

from app.agents.state import BannerAssets, Concept
from app.services.banners.html_renderer import render_banner_preview


def _concept() -> Concept:
    return Concept(
        layout="hero-left",
        copy={
            "eyebrow": "VIP deal",
            "headline": "Move brighter <script>alert(1)</script>",
            "subheadline": "40% off premium runners & apparel",
            "cta": "Shop now",
        },
        palette_usage={"background": "Cream", "text": "Ink", "cta_background": "Blue", "cta_text": "White"},
        image_prompt="premium running background",
        hierarchy_notes="headline first",
    )


def _assets() -> BannerAssets:
    return BannerAssets(
        webp={320: "https://cdn.example/banner-320.webp", 1280: "https://cdn.example/banner-1280.webp"},
        avif={},
        fallback_jpg={1280: "https://cdn.example/banner-1280.jpg"},
        alt_text_suggestion="Runner tying shoes in warm light",
        total_weight_kb_1280_webp=142.5,
        optimization_report={"avif_skipped": True, "avif_skip_reason": "pillow codec unavailable"},
    )


def _brand() -> dict:
    return {
        "name": "Demo Brand",
        "palette": [
            {"name": "Cream", "hex": "#F4F1EA"},
            {"name": "Ink", "hex": "#111111"},
            {"name": "Blue", "hex": "#123456"},
            {"name": "White", "hex": "#FFFFFF"},
        ],
    }


def test_html_renderer_escapes_copy_and_keeps_copy_as_html_text() -> None:
    rendered = render_banner_preview(_concept(), _assets(), brand=_brand())

    assert "<script>alert" not in rendered.html
    assert "Move brighter &lt;script&gt;alert(1)&lt;/script&gt;" in rendered.html
    assert "<h1 id=\"aij-banner-title\">" in rendered.html
    assert "background-image:" in rendered.html
    assert "srcset=\"https://cdn.example/banner-320.webp 320w" in rendered.html
    assert "Runner tying shoes" in rendered.html


def test_html_renderer_is_deterministic_and_reports_avif_skip() -> None:
    first = render_banner_preview(_concept(), _assets(), brand=_brand())
    second = render_banner_preview(_concept(), _assets(), brand=_brand())

    assert first.html == second.html
    assert first.metadata["avif_skipped"] is True
    assert first.metadata["breakpoints"] == [320, 1280]
    assert "application/ld+json" in first.html


def test_html_renderer_resolves_color_system_variants_before_palette() -> None:
    concept = _concept().model_copy(update={"palette_usage": {"background": "Soft Cream", "text": "primary", "cta_background": "Action Amber", "cta_text": "White"}})
    brand = {
        **_brand(),
        "color_system": {
            "primary": {"key": "primary", "label": "Trust Blue", "hex": "#123456", "variants": []},
            "secondary": {"key": "secondary", "label": "Warm Cream", "hex": "#F4F1EA", "variants": [{"name": "Soft Cream", "hex": "#FFF6E6"}]},
            "tertiary": {"key": "tertiary", "label": "Sun Accent", "hex": "#FFAA00", "variants": [{"name": "Action Amber", "hex": "#FF8800"}]},
        },
    }

    rendered = render_banner_preview(concept, _assets(), brand=brand)

    assert "--aij-bg:#FFF6E6" in rendered.html
    assert "--aij-text:#123456" in rendered.html
    assert "--aij-cta-bg:#FF8800" in rendered.html


def test_html_renderer_keeps_legacy_palette_only_lookup() -> None:
    rendered = render_banner_preview(_concept(), _assets(), brand=_brand())

    assert "--aij-bg:#F4F1EA" in rendered.html
    assert "--aij-text:#111111" in rendered.html
