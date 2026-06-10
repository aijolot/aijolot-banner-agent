"""placement-plan-recommend: el agente propone dónde/cuántas/formato desde el brief."""

from __future__ import annotations

import asyncio

from app.workflows.banner_creation import _load_runtime_skill

skill = _load_runtime_skill("placement-plan-recommend")


def _rec(brief: dict, *, creative_mode: str = "composite"):
    return asyncio.run(skill.recommend({"structured_brief": brief}, None, creative_mode=creative_mode))


def test_minimal_brief_gets_hero_only() -> None:
    plan = _rec({"goal": "Campaña general", "urgency": "low"})
    assert [p.placement_key for p in plan.pieces] == ["hero_main"]
    hero = plan.pieces[0]
    assert hero.priority == 1
    assert hero.format == "1440×420px (desktop)"  # dimensiones reales del catálogo
    assert hero.target == "home"
    assert plan.source == "deterministic"


def test_hero_inherits_campaign_creative_mode() -> None:
    plan = _rec({"goal": "Campaña de moda"}, creative_mode="full_picture")
    assert plan.pieces[0].creative_mode == "full_picture"


def test_rich_brief_proposes_multi_piece_set() -> None:
    brief = {
        "goal": "Buen Fin", "urgency": "high", "promo": "30% OFF",
        "products": [
            {"product_title": "Perfume Uno", "product_gid": "gid://shopify/Product/1"},
            {"product_title": "Perfume Dos", "product_gid": "gid://shopify/Product/2"},
        ],
    }
    plan = _rec(brief)
    keys = [p.placement_key for p in plan.pieces]
    assert keys == ["hero_main", "collection_header", "announcement_bar", "pdp_cross_sell"]
    assert [p.priority for p in plan.pieces] == [1, 2, 3, 4]
    assert all(p.rationale for p in plan.pieces)
    assert all(p.format for p in plan.pieces)
    # Cada pieza tiene slot real del catálogo para poder aplicarse como placement.
    assert all(p.slot for p in plan.pieces)


def test_promo_without_products_adds_announcement_bar() -> None:
    plan = _rec({"goal": "Sale", "promo": "2x1"})
    keys = [p.placement_key for p in plan.pieces]
    assert keys == ["hero_main", "announcement_bar"]


def test_plan_phase_exposes_placement_plan() -> None:
    from app.services.banners.revision_service import RevisionService
    from tests.unit.test_run_orchestrator import CAMPAIGN_ID, _build_service

    service, campaigns, revisions, variants, layouts, _audits = _build_service()
    campaigns.rows[CAMPAIGN_ID]["structured_brief"]["promo"] = "20% OFF"
    campaigns.rows[CAMPAIGN_ID]["structured_brief"]["products"] = [
        {"product_title": "Afnan 9PM", "product_gid": "gid://shopify/Product/77"}
    ]

    class _NoRefinements:
        def create(self, *, data):
            return {**data, "id": "rr-1"}
        def get(self, *, refinement_request_id):
            return None
        def update(self, *, refinement_request_id, data):
            return None

    revisions.list_by_campaign_id = lambda *, campaign_id: [  # type: ignore[attr-defined]
        r for r in revisions.rows.values() if str(r.get("campaign_id")) == campaign_id
    ]
    rev_service = RevisionService(
        campaigns=campaigns, revisions=revisions, variants=variants, layout_variants=layouts,
        refinement_requests=_NoRefinements(), generation_runs=service, team_id="team-1",
    )
    rev_service.start_plan_run(CAMPAIGN_ID)
    plan = rev_service.get_plan(CAMPAIGN_ID)
    pieces = plan.placement_plan.get("pieces") or []
    assert [p["placement_key"] for p in pieces][:2] == ["hero_main", "collection_header"]
    assert pieces[0]["priority"] == 1
