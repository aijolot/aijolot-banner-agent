"""Standalone banner HTML render + per-breakpoint aspect (no browser/vision).

render_banner_html runs the single-source JS template via Node, so the render
tests skip when Node is unavailable; aspect_for is pure Python and always runs.
"""
import shutil

import pytest

from app.services.banners.banner_render import render_banner_html, aspect_for, BREAKPOINTS

_needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

_SPEC = {
    "headline": "Frescura cítrica", "eyebrow": "verano", "sub": "Sub copy", "cta": "Compra ya",
    "promo": "Compra con 15% OFF", "imageUrl": "http://127.0.0.1:55321/x/hero.png",
    "bgCss": ".aijolot-banner{background:#FFD23F;color:#111}", "displayFont": "Sora", "bodyFont": "DM Sans",
    "textColor": "#111111", "layout": {"textX": 8, "heroX": 74, "aspectRatioTablet": 0.9},
}


@_needs_node
def test_desktop_is_horizontal_absolute():
    html = render_banner_html(_SPEC, breakpoint="desktop")
    assert 'class="hb-banner hb-live"' in html          # not the stack variant
    assert '<div class="hb-stack-inner">' not in html   # no stacked DOM
    assert '<div class="hb-live-copy" style="left:8' in html  # absolute %-positioned copy
    assert "1440px" in html
    assert ".hb-bg{background:#FFD23F" in html           # bg rescoped onto .hb-bg
    assert "15%" in html                                 # discount parsed from promo


@_needs_node
def test_tablet_is_stacked():
    html = render_banner_html(_SPEC, breakpoint="tablet")
    assert "hb-banner hb-live hb-live-stack" in html
    assert '<div class="hb-stack-inner">' in html
    assert "hb-stack-hero" in html


@_needs_node
def test_styled_headline_runs_and_hero_behind():
    spec = {
        **_SPEC,
        "headlineRuns": [{"text": "Frescura", "b": True, "color": "#FF2E93", "scale": 1.3}, {"text": "cítrica"}],
        "layout": {**_SPEC["layout"], "heroBehind": True, "heroW": 70},
    }
    html = render_banner_html(spec, breakpoint="desktop")
    assert "font-weight:900" in html and "color:#FF2E93" in html  # emphasis run styled
    assert "z-index:1" in html  # hero placed BEHIND the copy


@_needs_node
def test_styled_headline_rejects_bad_color():
    spec = {**_SPEC, "headlineRuns": [{"text": "x", "color": "javascript:alert(1)"}]}
    html = render_banner_html(spec, breakpoint="desktop")
    assert "javascript" not in html  # unsafe color dropped


def test_aspect_override_from_layout():
    assert aspect_for("tablet", {"aspectRatioTablet": 0.9}) == 0.9
    assert aspect_for("tablet", None) == BREAKPOINTS["tablet"][1]
    assert aspect_for("desktop", {}) == 2.4


@_needs_node
def test_escapes_headline():
    html = render_banner_html({**_SPEC, "headline": "<script>x</script>"}, breakpoint="mobile")
    assert "<script>x" not in html
