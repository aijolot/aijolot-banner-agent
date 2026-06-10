"""placement-plan-recommend skill — the agent proposes WHERE/HOW MANY/FORMAT.

Deterministic brief-driven rules (always available) + optional Gemini FLASH
refinement. Formats come from the real placement-type catalog dimensions.
"""

from __future__ import annotations

from typing import Any

from app.agents.tools import gemini_text
from app.schemas.placement_plan import PlacementPiece, PlacementPlanProposal

EST_PLACEMENT_PLAN_USD = 0.001
MAX_PIECES = 4


def _catalog() -> dict[str, dict[str, Any]]:
    from app.services.banners.placement_service import SEED_PLACEMENT_TYPES

    return {str(row["key"]): row for row in SEED_PLACEMENT_TYPES if row.get("is_active", True)}


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        brief = obj.get("structured_brief")
        if isinstance(brief, dict) and key in brief:
            return brief.get(key, default)
        return obj.get(key, default)
    return getattr(obj, key, default)


def _format_for(entry: dict[str, Any]) -> str:
    dims = (entry.get("default_dimensions") or {}).get("desktop") or {}
    width, height = dims.get("width"), dims.get("height")
    return f"{width}×{height}px (desktop)" if width and height else ""


def _piece(key: str, *, priority: int, creative_mode: str, rationale: str, target: str | None = None) -> PlacementPiece | None:
    entry = _catalog().get(key)
    if entry is None:
        return None
    targets = list(entry.get("supported_targets") or ["home"])
    slots = list(entry.get("supported_slots") or [])
    chosen_target = target if target in targets else targets[0]
    return PlacementPiece(
        placement_key=key,
        label=str(entry.get("label") or key),
        target=chosen_target,
        slot=str((slots[0] or {}).get("key") or "") if slots else "",
        format=_format_for(entry),
        creative_mode=creative_mode,
        priority=priority,
        rationale=rationale[:200],
    )


def fallback_plan(campaign: Any, *, creative_mode: str = "composite") -> PlacementPlanProposal:
    """Brief-driven deterministic pieces (see SKILL.md rules)."""
    products = _get(campaign, "products", []) or []
    n_products = len(products) if isinstance(products, list) else 0
    urgency = str(_get(campaign, "urgency", "")).lower()
    promo = str(_get(campaign, "promo", "") or "").strip()

    pieces: list[PlacementPiece] = []
    hero = _piece(
        "hero_main", priority=1, creative_mode=creative_mode,
        rationale="La pieza principal de la campaña: máximo impacto above-the-fold en la home.",
        target="home",
    )
    if hero:
        pieces.append(hero)
    if n_products >= 1:
        coll = _piece(
            "collection_header", priority=2, creative_mode="composite",
            rationale="Los productos del brief merecen su colección vestida con el mismo look de campaña.",
        )
        if coll:
            pieces.append(coll)
    if urgency == "high" or promo:
        bar = _piece(
            "announcement_bar", priority=len(pieces) + 1, creative_mode="composite",
            rationale=("La promo se refuerza en toda la tienda con una franja global." if promo
                       else "La urgencia amerita presencia global en la tienda."),
        )
        if bar:
            pieces.append(bar)
    if n_products >= 2:
        cross = _piece(
            "pdp_cross_sell", priority=len(pieces) + 1, creative_mode="composite",
            rationale="Con varios productos, el cross-sell en PDP multiplica el alcance de la campaña.",
        )
        if cross:
            pieces.append(cross)

    pieces = pieces[:MAX_PIECES]
    return PlacementPlanProposal(
        pieces=pieces,
        rationale=f"{len(pieces)} pieza(s) derivadas del brief: hero siempre; colección/franja/cross-sell según productos, promo y urgencia.",
        source="deterministic",
    )


def _build_prompt(campaign: Any, brand_context: Any, creative_mode: str) -> str:
    catalog_lines = "\n".join(
        f"- {key}: {entry.get('label')} — {entry.get('description')} (targets: {', '.join(entry.get('supported_targets') or [])}; {_format_for(entry)})"
        for key, entry in _catalog().items()
    )
    products = _get(campaign, "products", []) or []
    product_names = ", ".join(str((p or {}).get("product_title", "")) for p in products if isinstance(p, dict))
    return (
        "You are an ecommerce media planner. Choose the SET of banner pieces (1-4) for ONE campaign on a "
        "Shopify store, from THIS placement catalog ONLY:\n" + catalog_lines + "\n\n"
        f"Campaign goal: {_get(campaign, 'goal', '')}\nAudience: {_get(campaign, 'audience', '')}\n"
        f"Urgency: {_get(campaign, 'urgency', '')}\nPromo: {_get(campaign, 'promo', '')}\n"
        f"Products: {product_names or 'none specified'}\nDeadline: {_get(campaign, 'deadline', '')}\n"
        f"Recommended creative mode for the hero: {creative_mode}\n\n"
        "Rules: piece with priority 1 is the one built FIRST (usually hero_main). Pick only placements that "
        "genuinely serve this brief — fewer, well-justified pieces beat many. For each piece return "
        "placement_key (from the catalog), target, creative_mode (composite|full_picture|video; video only if "
        "the hero mode is video), priority (1..n) and a ONE-sentence rationale in Spanish. "
        "Return JSON {pieces:[...], rationale} matching the schema."
    )


async def recommend(
    campaign: Any,
    brand_context: Any = None,
    *,
    creative_mode: str = "composite",
    settings: Any = None,
    cost_guard: Any = None,
) -> PlacementPlanProposal:
    fallback = fallback_plan(campaign, creative_mode=creative_mode)
    if settings is None or not getattr(settings, "has_google_api_key", lambda: False)():
        return fallback
    try:
        from app.services.gemini.cost_guard import get_default_cost_guard

        guard = cost_guard or get_default_cost_guard(settings)
        if not guard.check_and_reserve(EST_PLACEMENT_PLAN_USD).allowed:
            return fallback
        result = await gemini_text.generate(
            _build_prompt(campaign, brand_context, creative_mode),
            model=gemini_text.FLASH_MODEL,
            structured=PlacementPlanProposal,
        )
    except gemini_text.GeminiUnavailable:
        return fallback
    except Exception:  # noqa: BLE001 — any failure → deterministic plan
        return fallback
    if not isinstance(result, PlacementPlanProposal):
        return fallback

    # Sanitize: only catalog keys, real formats/labels/slots, priorities normalized.
    catalog = _catalog()
    pieces: list[PlacementPiece] = []
    seen: set[str] = set()
    for raw in sorted(result.pieces, key=lambda p: p.priority)[:MAX_PIECES]:
        if raw.placement_key not in catalog or raw.placement_key in seen:
            continue
        seen.add(raw.placement_key)
        piece = _piece(
            raw.placement_key,
            priority=len(pieces) + 1,
            creative_mode=raw.creative_mode,
            rationale=raw.rationale or "",
            target=raw.target or None,
        )
        if piece:
            pieces.append(piece)
    if not pieces:
        return fallback
    return PlacementPlanProposal(pieces=pieces, rationale=(result.rationale or "")[:280], source="gemini")
