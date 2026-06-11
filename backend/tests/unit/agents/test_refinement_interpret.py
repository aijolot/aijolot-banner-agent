"""W0.1 — refinement-interpret: grounded routing of refinement feedback.

Covers the two real-world failures that motivated the skill:
1. "la fuente negra no contrasta bien"  → set_ink (NOT a background regen)
2. "cambia el SVG de círculo por una estrella de mar" → change_decor (NOT a background regen)
Both must work deterministically (no API key) via the extended keyword router.
"""

from __future__ import annotations

import asyncio

import pytest

from app.workflows.banner_creation import _load_runtime_skill

interpret_skill = _load_runtime_skill("refinement-interpret")
route_skill = _load_runtime_skill("refinement-route")


def _interpret(prompt: str, **kwargs):
    return asyncio.run(interpret_skill.interpret(prompt, **kwargs))


# --- deterministic fallback (no settings → no LLM) -------------------------


def test_contrast_complaint_routes_to_ink_not_background():
    plan = _interpret("la fuente negra no contrasta bien")
    assert plan.source == "deterministic"
    assert "set_ink" in plan.op_names()
    assert "change_background" not in plan.op_names()
    assert "redraft_concept" not in plan.op_names()


def test_svg_swap_routes_to_decor_not_background():
    plan = _interpret("cambia el SVG de círculo por una estrella de mar")
    assert "change_decor" in plan.op_names()
    assert "change_background" not in plan.op_names()
    decor = next(o for o in plan.ops if o.op == "change_decor")
    assert "estrella" in (decor.instruction or "")


def test_background_request_still_routes_to_background():
    plan = _interpret("quiero un fondo más veraniego con gradiente")
    assert "change_background" in plan.op_names()


def test_unmatched_prompt_defaults_to_redraft():
    plan = _interpret("dale otra vuelta completa")
    # "vuelta" matches nothing → keyword default {concept, copy} → redraft + copy ops
    assert "redraft_concept" in plan.op_names()


def test_explicit_targets_are_authoritative_and_skip_llm():
    plan = _interpret("lo que sea", targets=["background"])
    assert plan.source == "explicit"
    assert plan.op_names() == ["change_background"]


def test_image_scene_complaint_routes_to_set_image_prompt():
    plan = _interpret("la imagen no refleja la campaña, quiero una escena del estadio")
    assert "set_image_prompt" in plan.op_names()
    assert "change_background" not in plan.op_names()
    op = next(o for o in plan.ops if o.op == "set_image_prompt")
    assert "estadio" in (op.instruction or "")


def test_explicit_image_target_maps_to_set_image_prompt():
    scene = "estadio de futbol lleno con confeti"
    plan = _interpret(scene, targets=["image"])
    assert plan.source == "explicit"
    assert plan.op_names() == ["set_image_prompt"]
    assert plan.ops[0].instruction == scene


def test_hex_color_in_prompt_lands_on_set_ink_value():
    plan = _interpret("el texto no contrasta, ponlo en #FFEE00")
    op = next(o for o in plan.ops if o.op == "set_ink")
    assert op.value == "#FFEE00"


def test_copy_color_phrase_does_not_trigger_copy_rewrite():
    plan = _interpret("cambia el color del texto, no se lee")
    assert "set_ink" in plan.op_names()
    assert "edit_copy" not in plan.op_names()


# --- keyword router extensions ----------------------------------------------


def test_route_has_ink_and_decor_targets():
    assert "ink" in route_skill.VALID_TARGETS
    assert "decor" in route_skill.VALID_TARGETS
    assert route_skill.route("no contrasta") == ["ink"]
    assert route_skill.route("cambia el círculo por una estrella") == ["decor"]


def test_route_legacy_behavior_unchanged():
    assert route_skill.route("haz el copy más urgente y cambia el fondo") == ["copy", "background"]
    assert route_skill.route("") == ["concept", "copy"]


def test_normalize_targets_filters_invalid():
    assert route_skill.normalize_targets(["ink", "bogus"], "x") == ["ink"]


# --- sanitization ------------------------------------------------------------


def test_plan_schema_rejects_invalid_op():
    from app.schemas.refinement import RefinementOp

    with pytest.raises(ValueError):
        RefinementOp(op="explode_banner")


def test_section_whitelist():
    from app.schemas.refinement import RefinementOp

    assert RefinementOp(op="set_ink", section="headline").section == "headline"
    assert RefinementOp(op="set_ink", section="ALL").section is None
    assert RefinementOp(op="set_ink", section="weird").section is None
