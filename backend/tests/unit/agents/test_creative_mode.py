"""C0 — creative-mode-recommend: deterministic rules, gating, plan integration."""

from __future__ import annotations

import asyncio

from app.workflows.banner_creation import _load_runtime_skill

skill = _load_runtime_skill("creative-mode-recommend")


class _Settings:
    def __init__(self, *, video: bool = False):
        self.video_generation_enabled = video

    def has_google_api_key(self) -> bool:
        return False


def _rec(brief: dict, *, placement: str = "", video: bool = False):
    campaign = {"structured_brief": brief}
    return asyncio.run(skill.recommend(campaign, None, placement=placement, settings=_Settings(video=video)))


def test_fashion_brief_recommends_full_picture_with_humans() -> None:
    rec = _rec({"goal": "Lanzamiento colección de moda primavera", "audience": "Mujeres 25-40", "tone": "aspiracional"})
    assert rec.creative_mode == "full_picture"
    assert rec.include_humans is True
    assert rec.source == "deterministic"
    assert rec.rationale


def test_hardware_brief_recommends_composite_without_humans() -> None:
    rec = _rec({"goal": "Promoción de herramientas eléctricas", "audience": "contratistas"})
    assert rec.creative_mode == "composite"
    assert rec.include_humans is False


def test_video_is_gated_behind_setting() -> None:
    brief = {"goal": "Video teaser del lanzamiento", "placement": "hero_main"}
    assert _rec(brief, placement="hero_main", video=False).creative_mode != "video"
    assert _rec(brief, placement="hero_main", video=True).creative_mode == "video"


def test_unknown_vertical_defaults_to_composite() -> None:
    rec = _rec({"goal": "Promo general", "audience": "todos"})
    assert rec.creative_mode == "composite"
    assert rec.include_humans is False


# --- plan-phase integration ---------------------------------------------------


def test_plan_carries_creative_mode_and_user_override_wins() -> None:
    from app.services.banners.revision_service import RevisionService
    from tests.unit.test_run_orchestrator import CAMPAIGN_ID, _build_service

    service, campaigns, revisions, variants, layouts, _audits = _build_service()
    campaigns.rows[CAMPAIGN_ID]["structured_brief"]["goal"] = "Lanzamiento colección de moda"

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
    assert plan.creative_mode == "full_picture"
    assert plan.include_humans is True
    assert plan.mode_source == "agent"
    assert plan.mode_rationale

    # User override via the art_directions row → next plan respects it verbatim.
    class _StoredArt:
        def get_by_campaign_id(self, *, campaign_id):
            return {"creative_mode": "composite", "include_humans": False, "mode_source": "user"}

    service.orchestrator.art_directions = _StoredArt()
    rev_service.iterate_plan(CAMPAIGN_ID, __import__("app.schemas.generation", fromlist=["RegenerateRequest"]).RegenerateRequest(prompt="aplica el modo", target_nodes=["concept"]))
    plan2 = rev_service.get_plan(CAMPAIGN_ID)
    assert plan2.creative_mode == "composite"
    assert plan2.include_humans is False
    assert plan2.mode_source == "user"
