"""Standalone banner HTML render + per-breakpoint aspect (no browser/vision)."""
from app.services.banners.banner_render import render_banner_html, aspect_for, BREAKPOINTS

_SPEC = {
    "headline": "Frescura cítrica", "eyebrow": "verano", "sub": "Sub copy", "cta": "Compra ya",
    "promo": "Compra con 15% OFF", "imageUrl": "http://127.0.0.1:55321/x/hero.png",
    "bgCss": ".aijolot-banner{background:#FFD23F;color:#111}", "displayFont": "Sora", "bodyFont": "DM Sans",
    "textColor": "#111111", "layout": {"textX": 8, "heroX": 74, "aspectRatioTablet": 0.9},
}

def test_desktop_is_horizontal_absolute():
    html = render_banner_html(_SPEC, breakpoint="desktop")
    assert 'class="hb-banner hb-live"' in html          # not the stack variant
    assert '<div class="hb-stack-inner">' not in html   # no stacked DOM
    assert '<div class="hb-live-copy" style="left:8' in html  # absolute %-positioned copy
    assert "1440px" in html
    assert ".hb-bg{background:#FFD23F" in html           # bg rescoped onto .hb-bg
    assert "15%" in html                                 # discount parsed from promo

def test_tablet_is_stacked():
    html = render_banner_html(_SPEC, breakpoint="tablet")
    assert "hb-banner hb-live hb-live-stack" in html
    assert '<div class="hb-stack-inner">' in html
    assert "hb-stack-hero" in html

def test_aspect_override_from_layout():
    assert aspect_for("tablet", {"aspectRatioTablet": 0.9}) == 0.9
    assert aspect_for("tablet", None) == BREAKPOINTS["tablet"][1]
    assert aspect_for("desktop", {}) == 2.4

def test_escapes_headline():
    html = render_banner_html({**_SPEC, "headline": "<script>x</script>"}, breakpoint="mobile")
    assert "<script>x" not in html
