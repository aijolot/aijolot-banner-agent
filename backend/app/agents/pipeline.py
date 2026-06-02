"""ADK pipeline composition using Workflow (non-deprecated API).

Builds two Workflow graphs:
  - pre_review: nodes 1, 3-9 (runs until audit, pauses for HITL)
  - post_review: nodes 11-12 (runs after human approval)

Node 2 (campaign-intake) is multi-turn and handled by the API SSE
endpoint — it is NOT part of the pipeline. The campaign must be
complete in session.state before starting.

Graph topology:

    pre_review (Workflow)
    ┌─────────────────────────────────────────────────────────────┐
    │ START → brand_load → personalization → best_practices       │
    │   → concept_draft → prompt_refine → image_gen → image_opt  │
    │   → (html_render, liquid_build) → render_join               │
    │   → audit → {"pass": END, "retry": concept_draft}           │
    └─────────────────────────────────────────────────────────────┘

    post_review (Workflow)
    ┌───────────────────────────────────────┐
    │ START → schedule_route → publish      │
    └───────────────────────────────────────┘
"""

from __future__ import annotations

import time
from typing import Any

from google.adk.agents.context import Context
from google.adk.workflow import FunctionNode, JoinNode, Workflow

from app.agents import state_bridge as sb
from app.agents.tools import audit_log


# ── Helpers ───────────────────────────────────────────────────────

async def _emit_start(ctx: Context, node_key: str) -> None:
    await audit_log.emit(
        trace_id=ctx.state.get("trace_id", ""),
        session_id=ctx.state.get("session_id", ""),
        brand_id=ctx.state.get("brand_id", ""),
        node=node_key,
        event="node_started",
    )


async def _emit_done(ctx: Context, node_key: str, t0: float) -> None:
    await audit_log.emit(
        trace_id=ctx.state.get("trace_id", ""),
        session_id=ctx.state.get("session_id", ""),
        brand_id=ctx.state.get("brand_id", ""),
        node=node_key,
        event="node_completed",
        duration_ms=int((time.monotonic() - t0) * 1000),
    )


def _load_skill(skill_id: str):
    from app.agents.skill_agent import _load_skill_module
    return _load_skill_module(skill_id)


# ── Node functions ────────────────────────────────────────────────
# Each reads from ctx.state, calls skill.run(), writes back.
# FunctionNode auto-captures ctx.state mutations as state_delta.

async def node_brand_load(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "load_brand_context")
    kwargs = sb.read_brand_context_load(ctx.state)
    result = await _load_skill("brand-context-load").run(**kwargs)
    for k, v in sb.write_brand_context_load(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "load_brand_context", t0)


async def node_personalization(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "capture_user_personalization")
    kwargs = sb.read_user_personalization(ctx.state)
    result = await _load_skill("user-personalization").run(**kwargs)
    for k, v in sb.write_user_personalization(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "capture_user_personalization", t0)


async def node_best_practices(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "research_best_practices")
    kwargs = sb.read_best_practices(ctx.state)
    result = await _load_skill("best-practices-retrieve").run(**kwargs)
    for k, v in sb.write_best_practices(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "research_best_practices", t0)


async def node_concept_draft(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "draft_banner_concept")
    kwargs = sb.read_concept_draft(ctx.state)
    result = await _load_skill("banner-concept-draft").run(**kwargs)
    for k, v in sb.write_concept_draft(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "draft_banner_concept", t0)


async def node_prompt_refine(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "refine_image_prompt")
    kwargs = sb.read_image_prompt_refine(ctx.state)
    result = await _load_skill("image-prompt-refine").run(**kwargs)
    for k, v in sb.write_image_prompt_refine(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "refine_image_prompt", t0)


async def node_image_gen(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "generate_image")
    kwargs = sb.read_image_generate(ctx.state)
    result = await _load_skill("nano-banana-image-generate").run(**kwargs)
    for k, v in sb.write_image_generate(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "generate_image", t0)


async def node_image_opt(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "optimize_assets")
    kwargs = sb.read_image_optimize(ctx.state)
    result = await _load_skill("image-asset-optimize").run(**kwargs)
    for k, v in sb.write_image_optimize(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "optimize_assets", t0)


async def node_html_render(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "render_html")
    kwargs = sb.read_html_render(ctx.state)
    result = await _load_skill("banner-html-seo-render").run(**kwargs)
    for k, v in sb.write_html_render(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "render_html", t0)


async def node_liquid_build(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "render_liquid")
    kwargs = sb.read_liquid_build(ctx.state)
    result = await _load_skill("liquid-section-build").run(**kwargs)
    for k, v in sb.write_liquid_build(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "render_liquid", t0)


_DECISION_RETRY_TARGETS: dict[str, str] = {
    "retry_node_5": "draft_banner_concept",
    "retry_node_8": "render_html",
}


async def node_audit(ctx: Context) -> None:
    """Audit node with conditional routing for retry loop.

    Sets ctx.route to control the Workflow graph:
    - "pass" → exit to hitl_review (audit passed, warn, or escalated)
    - "retry" → loop back to concept_draft
    """
    t0 = time.monotonic()
    await _emit_start(ctx, "audit")
    kwargs = sb.read_performance_audit(ctx.state)
    result = await _load_skill("performance-audit").run(**kwargs)
    for k, v in sb.write_performance_audit(ctx.state, result).items():
        ctx.state[k] = v

    # Determine routing using explicit retry_target lookup
    decision = ctx.state.get("audit_decision", "human_review_required")
    retry_target = _DECISION_RETRY_TARGETS.get(decision)

    if retry_target is None:
        # pass, human_review_required, escalate_hitl → exit loop
        ctx.route = "pass"
    else:
        # Check retry budget for the specific target node
        retries = dict(ctx.state.get("retries", {}))
        current = retries.get(retry_target, 0)
        if current >= 2:
            ctx.state["audit_decision"] = "escalate_hitl"
            ctx.route = "pass"
        else:
            retries[retry_target] = current + 1
            ctx.state["retries"] = retries
            ctx.route = "retry"

    await _emit_done(ctx, "audit", t0)


async def node_schedule_route(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "schedule_or_publish")
    kwargs = sb.read_schedule_route(ctx.state)
    result = await _load_skill("schedule-or-publish-route").run(**kwargs)
    for k, v in sb.write_schedule_route(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "schedule_or_publish", t0)


async def node_shopify_publish(ctx: Context) -> None:
    t0 = time.monotonic()
    await _emit_start(ctx, "publish_to_shopify")
    kwargs = sb.read_shopify_publish(ctx.state)
    result = await _load_skill("shopify-theme-publish").run(**kwargs)
    for k, v in sb.write_shopify_publish(ctx.state, result).items():
        ctx.state[k] = v
    await _emit_done(ctx, "publish_to_shopify", t0)


# ── FunctionNode instances ────────────────────────────────────────

fn_brand_load = FunctionNode(func=node_brand_load, name="brand_load")
fn_personalization = FunctionNode(func=node_personalization, name="personalization")
fn_best_practices = FunctionNode(func=node_best_practices, name="best_practices")
fn_concept_draft = FunctionNode(func=node_concept_draft, name="concept_draft")
fn_prompt_refine = FunctionNode(func=node_prompt_refine, name="prompt_refine")
fn_image_gen = FunctionNode(func=node_image_gen, name="image_gen")
fn_image_opt = FunctionNode(func=node_image_opt, name="image_opt")
fn_html_render = FunctionNode(func=node_html_render, name="html_render")
fn_liquid_build = FunctionNode(func=node_liquid_build, name="liquid_build")
fn_audit = FunctionNode(func=node_audit, name="audit")
render_join = JoinNode(name="render_join")

async def node_hitl_review(ctx: Context) -> None:
    """Node 10 — HITL review gate.

    Marks the pipeline as awaiting human review. The actual pause
    happens at the pipeline boundary: the Workflow completes, the API
    stores the session state, and resumes post_review after the human
    decision arrives via the approval API.

    When GH-30 lands, this node will emit a RequestInput interrupt
    to pause the Workflow mid-execution and resume in-place.
    """
    t0 = time.monotonic()
    await _emit_start(ctx, "human_review")
    ctx.state["pipeline_status"] = "awaiting_review"
    ctx.state["hitl_status"] = "review_requested"
    await _emit_done(ctx, "human_review", t0)


fn_hitl_review = FunctionNode(func=node_hitl_review, name="hitl_review")
fn_schedule = FunctionNode(func=node_schedule_route, name="schedule_route")
fn_publish = FunctionNode(func=node_shopify_publish, name="shopify_publish")


# ── Pipeline builders ─────────────────────────────────────────────

def build_pre_review_pipeline() -> Workflow:
    """Pipeline: nodes 1, 3-9, 10 with creative-audit retry loop + HITL gate.

    Topology:
      START → brand_load → personalization → best_practices
        → concept_draft → prompt_refine → image_gen → image_opt
        → (html_render, liquid_build) → render_join
        → audit → {"pass": hitl_review, "retry": concept_draft}
    """
    return Workflow(
        name="pre_review_pipeline",
        edges=[
            # Linear pre-loop
            ("START", fn_brand_load, fn_personalization, fn_best_practices),
            # Creative sequence
            (fn_best_practices, fn_concept_draft, fn_prompt_refine,
             fn_image_gen, fn_image_opt),
            # Fan-out: parallel render
            (fn_image_opt, (fn_html_render, fn_liquid_build)),
            # Fan-in: join after both renders complete
            ((fn_html_render, fn_liquid_build), render_join),
            # Audit with conditional routing → HITL review on pass
            (render_join, fn_audit, {
                "pass": fn_hitl_review,
                "retry": fn_concept_draft,
            }),
        ],
    )


def build_post_review_pipeline() -> Workflow:
    """Pipeline: nodes 11-12 after HITL approval.

    Topology: START → schedule_route → shopify_publish → END
    """
    return Workflow(
        name="post_review_pipeline",
        edges=[
            ("START", fn_schedule, fn_publish),
        ],
    )
