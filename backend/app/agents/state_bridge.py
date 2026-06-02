"""State bridge — reader/writer functions for each skill node.

Each pair extracts the right kwargs from session.state for a skill's
run() function, and writes results back as a state delta dict.
"""

from __future__ import annotations

from typing import Any

from app.agents.state import BannerSessionState
from app.schemas.brand import BrandContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _brand_context(state: dict[str, Any]) -> BrandContext | None:
    bc = state.get("brand_context")
    if bc is None:
        return None
    if isinstance(bc, BrandContext):
        return bc
    return BrandContext.model_validate(bc)


def _to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj


# ---------------------------------------------------------------------------
# Node 1: brand-context-load
# ---------------------------------------------------------------------------

def read_brand_context_load(state: dict) -> dict:
    return {"brand_id": state.get("brand_id")}


def write_brand_context_load(state: dict, result: Any) -> dict:
    return {"brand_context": _to_dict(result)}


# ---------------------------------------------------------------------------
# Node 3: user-personalization
# ---------------------------------------------------------------------------

def read_user_personalization(state: dict) -> dict:
    return {"campaign": state.get("campaign", {})}


def write_user_personalization(state: dict, result: Any) -> dict:
    return {"variants": [_to_dict(v) for v in (result or [])]}


# ---------------------------------------------------------------------------
# Node 4: best-practices-retrieve
# ---------------------------------------------------------------------------

def read_best_practices(state: dict) -> dict:
    return {
        "campaign": state.get("campaign", {}),
        "brand_context": _brand_context(state),
    }


def write_best_practices(state: dict, result: Any) -> dict:
    return {"best_practices": result or []}


# ---------------------------------------------------------------------------
# Node 5: banner-concept-draft
# ---------------------------------------------------------------------------

def read_concept_draft(state: dict) -> dict:
    return {
        "campaign": state.get("campaign", {}),
        "brand_context": _brand_context(state),
        "variants": state.get("variants", []),
        "best_practices": state.get("best_practices", []),
    }


def write_concept_draft(state: dict, result: Any) -> dict:
    return {"concept": _to_dict(result)}


# ---------------------------------------------------------------------------
# Node 5.5: image-prompt-refine
# ---------------------------------------------------------------------------

def read_image_prompt_refine(state: dict) -> dict:
    return {
        "concept_or_prompt": state.get("concept", {}),
        "brand_context": _brand_context(state),
    }


def write_image_prompt_refine(state: dict, result: Any) -> dict:
    concept = dict(state.get("concept") or {})
    concept["image_prompt"] = result
    return {"concept": concept}


# ---------------------------------------------------------------------------
# Node 6: nano-banana-image-generate
# ---------------------------------------------------------------------------

def read_image_generate(state: dict) -> dict:
    concept = state.get("concept", {})
    return {"prompt": concept.get("image_prompt", "")}


def write_image_generate(state: dict, result: Any) -> dict:
    delta: dict[str, Any] = {}
    if isinstance(result, dict):
        delta["_image_bytes"] = result.get("image_bytes")
        delta["image_metadata"] = {
            k: v for k, v in result.items() if k != "image_bytes"
        }
    return delta


# ---------------------------------------------------------------------------
# Node 7: image-asset-optimize
# ---------------------------------------------------------------------------

def read_image_optimize(state: dict) -> dict:
    concept = state.get("concept", {})
    return {
        "image_bytes": state.get("_image_bytes", b""),
        "alt_text_hint": concept.get("copy", {}).get("headline", "Banner image"),
    }


def write_image_optimize(state: dict, result: Any) -> dict:
    return {"assets": _to_dict(result)}


# ---------------------------------------------------------------------------
# Node 8a: banner-html-seo-render
# ---------------------------------------------------------------------------

def read_html_render(state: dict) -> dict:
    from app.agents.state import BannerAssets, Concept
    return {
        "concept": Concept.model_validate(state["concept"]),
        "assets": BannerAssets.model_validate(state["assets"]),
        "brand": _brand_context(state),
    }


def write_html_render(state: dict, result: Any) -> dict:
    return {"html_standalone": result}


# ---------------------------------------------------------------------------
# Node 8b: liquid-section-build
# ---------------------------------------------------------------------------

def read_liquid_build(state: dict) -> dict:
    from app.agents.state import Concept, Variant
    variants = [Variant.model_validate(v) for v in state.get("variants", [])]
    return {
        "concept": Concept.model_validate(state["concept"]),
        "variants": variants,
        "brand": _brand_context(state),
    }


def write_liquid_build(state: dict, result: Any) -> dict:
    if isinstance(result, dict):
        return {"liquid_section": result.get("section", "")}
    return {"liquid_section": str(result or "")}


# ---------------------------------------------------------------------------
# Node 9: performance-audit
# ---------------------------------------------------------------------------

def read_performance_audit(state: dict) -> dict:
    from app.agents.state import BannerSessionState
    bss = BannerSessionState(
        trace_id=state.get("trace_id", ""),
        session_id=state.get("session_id", ""),
        brand_id=state.get("brand_id", ""),
    )
    if state.get("assets"):
        from app.agents.state import BannerAssets
        bss.assets = BannerAssets.model_validate(state["assets"])
    bss.retries = state.get("retries", {})
    return {
        "html": state.get("html_standalone", ""),
        "state": bss,
    }


def write_performance_audit(state: dict, result: Any) -> dict:
    if isinstance(result, tuple) and len(result) == 2:
        report, decision = result
        return {
            "audit_report": _to_dict(report),
            "audit_decision": decision,
        }
    return {"audit_report": _to_dict(result)}


# ---------------------------------------------------------------------------
# Node 11: schedule-or-publish-route
# ---------------------------------------------------------------------------

def read_schedule_route(state: dict) -> dict:
    from app.agents.state import BannerSessionState
    bss = BannerSessionState(
        trace_id=state.get("trace_id", ""),
        session_id=state.get("session_id", ""),
        brand_id=state.get("brand_id", ""),
    )
    return {"state": bss}


def write_schedule_route(state: dict, result: Any) -> dict:
    return {"publish_route": result}


# ---------------------------------------------------------------------------
# Node 12: shopify-theme-publish
# ---------------------------------------------------------------------------

def read_shopify_publish(state: dict) -> dict:
    from app.agents.state import BannerSessionState, HITLDecision
    bss = BannerSessionState(
        trace_id=state.get("trace_id", ""),
        session_id=state.get("session_id", ""),
        brand_id=state.get("brand_id", ""),
    )
    if state.get("hitl_decision"):
        bss.hitl_decision = HITLDecision.model_validate(state["hitl_decision"])
    return {"state": bss}


def write_shopify_publish(state: dict, result: Any) -> dict:
    return {"publish_result": _to_dict(result)}


# ---------------------------------------------------------------------------
# Pipeline initialization
# ---------------------------------------------------------------------------

def init_pipeline_state(
    *,
    trace_id: str,
    session_id: str,
    brand_id: str,
    campaign: dict[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    """Create the initial session.state dict for the pipeline."""
    return {
        "trace_id": trace_id,
        "session_id": session_id,
        "brand_id": brand_id,
        "campaign": campaign,
        "variants": [],
        "best_practices": [],
        "retries": {},
        "cost_usd_running": 0.0,
        **extra,
    }
