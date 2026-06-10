"""refinement-interpret skill (W0.1).

Interpret a free-text refinement prompt into a :class:`RefinementPlan` of
*directed operations* so plan-iterate / refine only touches what the user asked
for. Gemini FLASH (structured) when available; deterministic keyword routing
(``refinement-route``) as fallback. Explicit user targets are authoritative and
skip the LLM entirely.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.tools import gemini_text
from app.schemas.refinement import RefinementOp, RefinementPlan

EST_INTERPRET_USD = 0.001

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")

# target → op used when mapping legacy/keyword targets onto directed ops.
_TARGET_OPS: dict[str, str] = {
    "ink": "set_ink",
    "decor": "change_decor",
    "background": "change_background",
    "copy": "edit_copy",
    "layout": "adjust_layout",
    "concept": "redraft_concept",
}

# op → legacy target (for the ``targets`` routing field consumed downstream).
_OP_TARGETS: dict[str, str] = {v: k for k, v in _TARGET_OPS.items()}


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _hex_in(prompt: str) -> str | None:
    match = _HEX_RE.search(prompt or "")
    return match.group(0) if match else None


def _plan_from_targets(targets: list[str], prompt: str, *, source: str) -> RefinementPlan:
    """Map routing targets to directed ops (used for explicit targets + fallback)."""
    ops: list[RefinementOp] = []
    seen: set[str] = set()
    for target in targets:
        op_name = _TARGET_OPS.get(target)
        if not op_name or op_name in seen:
            continue
        seen.add(op_name)
        ops.append(
            RefinementOp(
                op=op_name,
                value=_hex_in(prompt) if op_name == "set_ink" else None,
                instruction=prompt or None,
            )
        )
    if not ops:
        ops = [RefinementOp(op="redraft_concept", instruction=prompt or None)]
    return RefinementPlan(
        targets=[_OP_TARGETS[o.op] for o in ops],
        ops=ops,
        rationale="keyword/explicit routing",
        source=source,
    )


def fallback_plan(prompt: str) -> RefinementPlan:
    """Deterministic interpretation via the keyword router (no LLM)."""
    from app.workflows.banner_creation import _load_runtime_skill

    route = _load_runtime_skill("refinement-route").route
    hits = route(prompt)
    return _plan_from_targets(hits, prompt, source="deterministic")


def _concept_summary(concept: dict[str, Any] | None) -> str:
    if not concept:
        return "(no previous concept)"
    copy = dict(concept.get("copy") or {})
    background = dict(concept.get("background") or {})
    art = dict(concept.get("art_direction") or {})
    fonts = dict(art.get("fonts") or {})
    bg_html = str(background.get("html") or "")
    has_svg = "<svg" in bg_html.lower() or "svg+xml" in str(background.get("css") or "").lower()
    lines = [
        f"Headline: {copy.get('headline', '')}",
        f"Subheadline: {copy.get('subheadline', '')}",
        f"Eyebrow: {copy.get('eyebrow', '')} · CTA: {copy.get('cta', '')}",
        f"Text ink color: {art.get('ink', '(auto)')}",
        f"Fonts: {fonts.get('display', '')}/{fonts.get('body', '')}",
        f"Layout: {concept.get('layout', '')}",
        f"Background: {background.get('name', '')} — {background.get('description', '')}"
        + (" (contains decorative SVG shapes)" if has_svg else ""),
    ]
    return "\n".join(lines)


def _build_prompt(prompt: str, concept: dict[str, Any] | None) -> str:
    return (
        "You are routing a user's banner-refinement request to the MINIMAL set of directed edit operations.\n"
        "The user is iterating on an ecommerce banner plan. Current state:\n"
        f"{_concept_summary(concept)}\n\n"
        f'User request (may be Spanish or English): "{prompt}"\n\n'
        "Available operations:\n"
        "- set_ink: change the TEXT color (contrast/legibility complaints, 'la fuente no contrasta', text color). "
        "value=hex if the user named a color, else empty for auto-contrast. section=headline|subheadline|eyebrow|cta "
        "only if the user singled one out.\n"
        "- change_decor: swap or edit DECORATIVE SHAPES/SVG motifs in the background (circles, stars, patterns) "
        "while keeping the background colors/gradient. instruction=what to swap, e.g. 'replace circle SVG with a starfish SVG'.\n"
        "- change_background: regenerate the background treatment (colors/gradient/mood). instruction=the user's direction.\n"
        "- edit_copy: rewrite copy text (headline/sub/eyebrow/CTA wording, tone, urgency). instruction required.\n"
        "- adjust_layout: composition/structure/position changes. instruction required.\n"
        "- redraft_concept: ONLY when the user wants a fundamentally different creative direction.\n\n"
        "Rules: choose the FEWEST ops that fully satisfy the request — do NOT add ops the user did not ask for. "
        "A text-contrast complaint is set_ink, NOT change_background. A shape/SVG swap is change_decor, NOT "
        "change_background. Keep instructions in the user's language. Return JSON matching the schema with "
        "targets=[] (it is derived server-side), ops, and a one-line rationale."
    )


def _sanitize(plan: RefinementPlan, prompt: str) -> RefinementPlan:
    ops: list[RefinementOp] = []
    seen: set[tuple[str, str | None]] = set()
    for op in plan.ops[:5]:
        key = (op.op, op.section)
        if key in seen:
            continue
        seen.add(key)
        value = op.value
        if op.op == "set_ink" and value is not None and not _HEX_RE.fullmatch(value.strip()):
            value = _hex_in(value) or _hex_in(prompt)
        ops.append(RefinementOp(op=op.op, section=op.section, value=value, instruction=op.instruction or prompt or None))
    if not ops:
        return fallback_plan(prompt)
    return RefinementPlan(
        targets=sorted({_OP_TARGETS[o.op] for o in ops}),
        ops=ops,
        rationale=(plan.rationale or "")[:280],
        source="gemini",
    )


async def interpret(
    prompt: str,
    *,
    targets: list[str] | None = None,
    concept: dict[str, Any] | None = None,
    settings: Any = None,
    cost_guard: Any = None,
) -> RefinementPlan:
    """Interpret ``prompt`` into a RefinementPlan.

    Explicit ``targets`` (user clicked a scoped control) are authoritative and
    bypass the LLM. Otherwise: Gemini FLASH structured → deterministic fallback.
    """
    if targets:
        return _plan_from_targets([t for t in targets if t in _TARGET_OPS], prompt, source="explicit")
    if not (prompt or "").strip():
        return fallback_plan(prompt)
    if settings is None or not getattr(settings, "has_google_api_key", lambda: False)():
        return fallback_plan(prompt)
    try:
        from app.services.gemini.cost_guard import get_default_cost_guard

        guard = cost_guard or get_default_cost_guard(settings)
        if not guard.check_and_reserve(EST_INTERPRET_USD).allowed:
            return fallback_plan(prompt)
        result = await gemini_text.generate(
            _build_prompt(prompt, concept),
            model=gemini_text.FLASH_MODEL,
            structured=RefinementPlan,
        )
    except gemini_text.GeminiUnavailable:
        return fallback_plan(prompt)
    except Exception:  # noqa: BLE001 — any failure → deterministic routing
        return fallback_plan(prompt)
    if not isinstance(result, RefinementPlan):
        return fallback_plan(prompt)
    return _sanitize(result, prompt)
