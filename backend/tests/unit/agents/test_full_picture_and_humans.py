"""C1/C3 — full-picture prompts, conditional people sanitization, adaptive contrast."""

from __future__ import annotations

import asyncio
import io

from app.workflows.banner_creation import _load_runtime_skill

refine = _load_runtime_skill("image-prompt-refine")


def _run(concept, art_direction=None, **kwargs):
    return asyncio.run(refine.run(concept, art_direction=art_direction, **kwargs))


CONCEPT = {"image_prompt": "a premium perfume moment", "layout": "Hero split layout"}


# --- C1: full-picture prompt branch ------------------------------------------


def test_full_picture_prompt_describes_full_scene_with_copy_zone():
    art = {"creative_mode": "full_picture", "layout": {"textX": 6, "textW": 48}}
    prompt = _run(CONCEPT, art)
    assert "FULL-BLEED" in prompt
    assert "LEFT third" in prompt  # copy zone derived from layout %
    assert "blank copy space for later HTML-rendered messaging" not in prompt
    assert "people-free" in prompt  # humans not allowed by default
    assert "chroma" not in prompt.lower()


def test_full_picture_copy_zone_follows_layout():
    right = _run(CONCEPT, {"creative_mode": "full_picture", "layout": {"textX": 60, "textW": 35}})
    assert "RIGHT third" in right
    center = _run(CONCEPT, {"creative_mode": "full_picture", "layout": {"textX": 30, "textW": 40}})
    assert "CENTER band" in center


def test_composite_mode_keeps_legacy_prompt_shape():
    prompt = _run(CONCEPT, {"creative_mode": "composite"})
    assert "blank copy space" in prompt
    assert "people-free" in prompt


# --- C3: humans allowed --------------------------------------------------------


def test_include_humans_drops_people_free_and_adds_representation_rules():
    art = {"creative_mode": "full_picture", "include_humans": True, "layout": {"textX": 6, "textW": 48}}
    prompt = _run(CONCEPT, art)
    assert "people-free" not in prompt
    assert "no minors" in prompt
    assert "no celebrity" in prompt
    assert "diverse casting" in prompt
    # text/logos/UI stay sanitized in BOTH modes.
    assert "mark-free" in prompt


def test_text_terms_sanitized_even_with_humans():
    concept = {"image_prompt": "scene with text and logo of the brand", "layout": ""}
    prompt = _run(concept, {"creative_mode": "full_picture", "include_humans": True})
    assert "logo of the brand" not in prompt
    assert " text " not in f" {prompt} ".lower().replace("context", "")


def test_faces_term_survives_when_humans_allowed_and_replaced_otherwise():
    concept = {"image_prompt": "happy faces enjoying the product", "layout": ""}
    with_humans = _run(concept, {"include_humans": True})
    without = _run(concept, {})
    assert "faces" in with_humans
    assert "faces" not in without
    assert "people-free scene" in without


# --- C1: adaptive contrast -----------------------------------------------------


def _png(color) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (160, 90), color).save(buf, format="PNG")
    return buf.getvalue()


def test_adaptive_ink_bright_zone_dark_ink_no_scrim():
    from app.services.banners.contrast import adaptive_ink_and_scrim

    result = adaptive_ink_and_scrim(_png((245, 245, 240)), {"textX": 6, "textY": 50, "textW": 48})
    assert result["ink"] == "#111111"
    assert result["scrim_alpha"] == 0.0


def test_adaptive_ink_dark_zone_light_ink_no_scrim():
    from app.services.banners.contrast import adaptive_ink_and_scrim

    result = adaptive_ink_and_scrim(_png((18, 22, 30)), {"textX": 6, "textY": 50, "textW": 48})
    assert result["ink"] == "#FFFFFF"
    assert result["scrim_alpha"] == 0.0


def test_adaptive_ink_midtone_gets_scrim_toward_copy_side():
    from app.services.banners.contrast import adaptive_ink_and_scrim

    result = adaptive_ink_and_scrim(_png((128, 128, 128)), {"textX": 60, "textY": 50, "textW": 35})
    assert result["ink"] == "#FFFFFF"
    assert 0.1 <= result["scrim_alpha"] <= 0.55
    assert result["scrim_dir"] == "270deg"  # copy on the right → darken from the right


# --- C1: live spec carries the full-bleed background ---------------------------


def test_review_spec_full_bleed_uses_background_image_not_cutout():
    from app.services.banners.run_orchestrator import RunOrchestrator

    class _Concept:
        copy = {"headline": "Hola", "subheadline": "", "eyebrow": "", "cta": "Compra"}
        layout = "Hero full bleed"

    spec = RunOrchestrator._banner_review_spec(
        _Concept(),
        {"name": "Escena completa generada", "css": "", "image_url": "https://cdn/scene.png"},
        [],
        {
            "full_bleed": True, "focal": {"x": 70, "y": 55}, "scrim": {"dir": "90deg", "alpha": 0.3},
            "fonts": {"display": "Syne", "body": "Inter"}, "layout": {"textX": 6}, "ink": "#FFFFFF",
        },
        "https://cdn/scene.png",
    )
    assert spec["bgImageUrl"] == "https://cdn/scene.png"
    assert spec["imageUrl"] is None  # no hero cut-out in full-picture mode
    assert spec["bgFocal"] == {"x": 70, "y": 55}
    assert spec["scrim"]["alpha"] == 0.3
    assert spec["textColor"] == "#FFFFFF"
