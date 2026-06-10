"""F5 — real generation orchestrator persists genuine artifacts.

These tests exercise the full pipeline with in-memory repositories and no
Supabase / no GOOGLE_API_KEY: the image step degrades to the free fake
provider, KG retrieval uses the static floor, and the deterministic creative
skills render a structurally real banner. We assert that a revision, banner +
layout variants, an audit report, and per-node events are all persisted, and
that the campaign points at the new revision.
"""

from __future__ import annotations

import copy
from uuid import uuid4

import pytest

from app.schemas.generation import GenerationRunCreate
from app.services.banners.generation_run_service import (
    GenerationRunService,
    InMemoryGenerationEventRepository,
    InMemoryGenerationRunRepository,
)
from app.services.banners.run_orchestrator import RunOrchestrator

CAMPAIGN_ID = "00000000-0000-0000-0000-000000000401"


class InMemoryCampaigns:
    def __init__(self) -> None:
        self.rows = {
            CAMPAIGN_ID: {
                "id": CAMPAIGN_ID,
                "team_id": "team-1",
                "title": "Promo de fin de semana",
                "status": "brief_ready",
                "selected_revision_id": None,
                "structured_brief": {
                    "goal": "Impulsar ventas de fin de semana",
                    "audience": "mujeres jóvenes",
                    "cta": "Comprar ya",
                    "tone": "energetic",
                    "urgency": "high",
                    "placement": "hero_main",
                },
            }
        }

    def get(self, *, campaign_id: str, team_id: str | None = None):
        return copy.deepcopy(self.rows.get(campaign_id))

    def update(self, *, campaign_id: str, data: dict, team_id: str | None = None):
        self.rows[campaign_id].update(data)
        return copy.deepcopy(self.rows[campaign_id])


class InMemoryRevisions:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def create(self, *, data: dict):
        row = {"id": str(uuid4()), "created_at": "2026-01-01T00:00:00+00:00", **data}
        self.rows[row["id"]] = row
        return copy.deepcopy(row)

    def get(self, *, revision_id: str):
        return copy.deepcopy(self.rows.get(revision_id))

    def get_latest_by_campaign_id(self, *, campaign_id: str):
        rows = [r for r in self.rows.values() if r["campaign_id"] == campaign_id]
        if not rows:
            return None
        return copy.deepcopy(max(rows, key=lambda r: r["revision_number"]))

    def update(self, *, revision_id: str, data: dict):
        self.rows[revision_id].update(data)
        return copy.deepcopy(self.rows[revision_id])


class InMemoryVariants:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def create_many(self, *, variants: list[dict]):
        created = []
        for row in variants:
            new = {"id": str(uuid4()), **row}
            self.rows[new["id"]] = new
            created.append(copy.deepcopy(new))
        return created

    def list_by_revision_id(self, *, revision_id: str):
        return copy.deepcopy([r for r in self.rows.values() if r["revision_id"] == revision_id])


class InMemoryLayoutVariants(InMemoryVariants):
    pass


class InMemoryAuditReports:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def create(self, *, data: dict):
        row = {"id": str(uuid4()), "created_at": "2026-01-01T00:00:00+00:00", **data}
        self.rows.append(copy.deepcopy(row))
        return copy.deepcopy(row)


def _build_service() -> tuple[GenerationRunService, InMemoryCampaigns, InMemoryRevisions, InMemoryVariants, InMemoryLayoutVariants, InMemoryAuditReports]:
    campaigns = InMemoryCampaigns()
    revisions = InMemoryRevisions()
    variants = InMemoryVariants()
    layouts = InMemoryLayoutVariants()
    audits = InMemoryAuditReports()
    orchestrator = RunOrchestrator(
        revisions=revisions,
        variants=variants,
        layout_variants=layouts,
        audit_reports=audits,
        campaigns=campaigns,
        asset_service=None,
        team_id="team-1",
    )
    service = GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns,
        orchestrator=orchestrator,
        team_id="team-1",
    )
    return service, campaigns, revisions, variants, layouts, audits


def test_orchestrated_run_persists_real_revision_and_artifacts() -> None:
    service, campaigns, revisions, variants, layouts, audits = _build_service()

    run = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(metadata={"source": "test"}))

    assert run.status == "succeeded"
    assert run.frontend_step == "review_publish"
    assert run.metadata["facade_version"] == "f5-run-orchestrator"
    assert run.metadata["source"] == "test"

    # A real revision was persisted and selected.
    assert len(revisions.rows) == 1
    revision = next(iter(revisions.rows.values()))
    assert revision["campaign_id"] == CAMPAIGN_ID
    assert revision["generation_run_id"] == run.id
    assert revision["revision_number"] == 1
    assert revision["status"] == "selected"
    assert revision["concept"]  # non-empty concept dict
    assert revision["html_preview"] and "<" in revision["html_preview"]
    assert revision["liquid_config"].get("section") is not None

    # Campaign points at the new revision.
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == revision["id"]
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "draft"

    # Banner + layout variants persisted.
    banner_rows = variants.list_by_revision_id(revision_id=revision["id"])
    assert len(banner_rows) == 1
    assert banner_rows[0]["headline"]
    layout_rows = layouts.list_by_revision_id(revision_id=revision["id"])
    assert {r["key"] for r in layout_rows} == {"A", "B", "C"}

    # Audit report persisted and FK-linked.
    assert len(audits.rows) == 1
    assert audits.rows[0]["revision_id"] == revision["id"]
    assert audits.rows[0]["generation_run_id"] == run.id
    assert audits.rows[0]["status"] in {"pending", "pass", "fail", "escalated"}


def test_orchestrated_run_emits_real_ordered_events() -> None:
    service, *_ = _build_service()

    run = service.start_generation_run(CAMPAIGN_ID)
    events = service.list_events(run.id)

    node_keys = [e.node_key for e in events]
    # Pipeline runs nodes load_brand_context .. audit, each started+succeeded.
    assert node_keys[0] == "load_brand_context"
    assert events[0].status == "started"
    assert ("audit", "succeeded") in [(e.node_key, e.status) for e in events]
    assert events[-1].node_key == "audit"
    assert events[-1].status == "succeeded"
    assert events[-1].frontend_step == "render_audit"
    # No deterministic Task-10 stub summaries leaked in.
    assert all("Deterministic Task 10" not in str(e.input_summary) for e in events)
    # Timestamps strictly ordered and unique.
    created = [e.created_at for e in events if e.created_at]
    assert created == sorted(created)
    assert len(set(created)) == len(created)


def test_refinement_run_keeps_deterministic_shell() -> None:
    """Refinement runs must NOT trigger the orchestrator (RevisionService owns them)."""
    service, _campaigns, revisions, *_ = _build_service()

    run = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(run_type="refinement"))

    assert run.metadata["facade_version"] == "task-10-deterministic"
    assert revisions.rows == {}  # orchestrator did not run


class InMemoryCatalog:
    def __init__(self, items, discount_rule=None) -> None:
        self._snapshot = {"id": "snap-1", "items": items, "discount_rule": discount_rule or {}}

    def get_latest_by_campaign_id(self, *, campaign_id):
        return copy.deepcopy(self._snapshot)


def test_concept_adapts_to_catalog_and_promo() -> None:
    campaigns = InMemoryCampaigns()
    campaigns.rows[CAMPAIGN_ID]["promo_label"] = "25% OFF"
    revisions = InMemoryRevisions()
    variants = InMemoryVariants()
    layouts = InMemoryLayoutVariants()
    audits = InMemoryAuditReports()
    catalog = InMemoryCatalog([{"title": "Afnan 9PM EDP 100ml", "price": 1299, "sale_price": 999}])
    orchestrator = RunOrchestrator(
        revisions=revisions, variants=variants, layout_variants=layouts, audit_reports=audits,
        campaigns=campaigns, catalog=catalog, asset_service=None, team_id="team-1",
    )
    service = GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns, orchestrator=orchestrator, team_id="team-1",
    )

    run = service.start_generation_run(CAMPAIGN_ID)
    assert run.status == "succeeded"
    revision = next(iter(revisions.rows.values()))
    copyd = revision["concept"]["copy"]
    # Headline grounds in the real catalog product; CTA carries the promo.
    assert "Afnan 9PM" in copyd["headline"]
    assert "25% OFF" in copyd["cta"]


def test_brief_products_ground_concept_without_catalog_snapshot() -> None:
    # Campaign-level products picked in the brief should ground the concept copy
    # even when there is NO catalog snapshot service wired.
    campaigns = InMemoryCampaigns()
    campaigns.rows[CAMPAIGN_ID]["structured_brief"]["products"] = [
        {"product_title": "Afnan 9PM EDP 100ml", "product_gid": "gid://shopify/Product/77", "price": "1,299"}
    ]
    campaigns.rows[CAMPAIGN_ID]["structured_brief"]["destination_url"] = "/collections/perfumes"
    revisions = InMemoryRevisions()
    variants = InMemoryVariants()
    layouts = InMemoryLayoutVariants()
    audits = InMemoryAuditReports()
    orchestrator = RunOrchestrator(
        revisions=revisions, variants=variants, layout_variants=layouts, audit_reports=audits,
        campaigns=campaigns, asset_service=None, team_id="team-1",  # no catalog
    )
    service = GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns, orchestrator=orchestrator, team_id="team-1",
    )

    run = service.start_generation_run(CAMPAIGN_ID)
    assert run.status == "succeeded"
    revision = next(iter(revisions.rows.values()))
    assert "Afnan 9PM" in revision["concept"]["copy"]["headline"]
    # Destination URL flows into the banner variant CTA link.
    rows = variants.list_by_revision_id(revision_id=revision["id"])
    assert rows and rows[0]["cta_url"] == "/collections/perfumes"


def test_generates_one_banner_variant_per_personalization_variant() -> None:
    campaigns = InMemoryCampaigns()
    campaigns.rows[CAMPAIGN_ID]["structured_brief"]["personalization_variants"] = [
        {"key": "male", "label": "Hombre", "audience": "hombres 18-30", "customer_tag": "gender:male"},
        {"key": "female", "label": "Mujer", "audience": "mujeres 18-30", "customer_tag": "gender:female"},
    ]
    revisions = InMemoryRevisions()
    variants = InMemoryVariants()
    layouts = InMemoryLayoutVariants()
    audits = InMemoryAuditReports()
    orchestrator = RunOrchestrator(
        revisions=revisions, variants=variants, layout_variants=layouts, audit_reports=audits,
        campaigns=campaigns, asset_service=None, team_id="team-1",
    )
    service = GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns, orchestrator=orchestrator, team_id="team-1",
    )

    run = service.start_generation_run(CAMPAIGN_ID)
    assert run.status == "succeeded"
    revision = next(iter(revisions.rows.values()))
    rows = variants.list_by_revision_id(revision_id=revision["id"])
    assert {r["segment_key"] for r in rows} == {"male", "female"}
    assert {r["customer_tag"] for r in rows} == {"gender:male", "gender:female"}
    assert all(r.get("headline") for r in rows)


async def _boom_no_image(**_kwargs):
    raise AssertionError("image work must not run in the plan phase")


def test_plan_phase_stops_before_image_and_does_not_promote() -> None:
    service, campaigns, revisions, variants, layouts, audits = _build_service()
    # Fail loudly if the plan phase reaches any image work.
    service.orchestrator._generate_image = _boom_no_image  # type: ignore[attr-defined]
    service.orchestrator._compose_variant_hero = _boom_no_image  # type: ignore[attr-defined]

    run, revision_id = service.start_plan_run(CAMPAIGN_ID)

    assert run.status == "succeeded"
    assert run.frontend_step == "concept"
    assert run.metadata["phase"] == "plan"
    assert run.metadata["awaiting_approval"] is True

    # A plan revision exists but is NOT promoted (no image/render/audit ran).
    assert revision_id is not None
    revision = revisions.rows[revision_id]
    assert revision["status"] == "plan"
    assert audits.rows == []
    assert variants.rows == {}
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] is None

    # No generate_image event leaked into the run.
    node_keys = [e.node_key for e in service.list_events(run.id)]
    assert "generate_image" not in node_keys
    assert node_keys[-1] == "draft_banner_concept"


def test_plan_phase_builds_wireframe_spec_without_image() -> None:
    service, _campaigns, revisions, *_ = _build_service()
    run, revision_id = service.start_plan_run(CAMPAIGN_ID)
    assert run.status == "succeeded"

    plan = revisions.rows[revision_id]["concept"]["plan"]
    assert plan["wireframe"]["imageUrl"] == ""
    assert plan["wireframe"]["headline"]
    assert plan["typography"]["display"]
    assert plan["copy_preview"]["headline"]
    assert plan["product_intent"]  # at least the default audience


def test_approve_resumes_into_build_and_promotes() -> None:
    service, campaigns, revisions, variants, layouts, audits = _build_service()
    _plan_run, plan_revision_id = service.start_plan_run(CAMPAIGN_ID)
    plan_revision = revisions.rows[plan_revision_id]

    run, revision_id = service.start_build_run(CAMPAIGN_ID, plan_revision=plan_revision)

    assert run.status == "succeeded"
    assert run.frontend_step == "review_publish"
    assert run.metadata["phase"] == "build"
    # Same revision, now promoted with real artifacts.
    assert revision_id == plan_revision_id
    revision = revisions.rows[plan_revision_id]
    assert revision["status"] == "selected"
    assert revision["html_preview"] and "<" in revision["html_preview"]
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == plan_revision_id
    # Build ran the image + audit nodes.
    node_keys = [e.node_key for e in service.list_events(run.id)]
    assert "generate_image" in node_keys
    assert len(audits.rows) == 1
    assert layouts.list_by_revision_id(revision_id=plan_revision_id)


def test_iterate_redrafts_plan_without_image_cost() -> None:
    service, _campaigns, revisions, *_ = _build_service()
    service.orchestrator._generate_image = _boom_no_image  # type: ignore[attr-defined]
    service.orchestrator._compose_variant_hero = _boom_no_image  # type: ignore[attr-defined]

    run1, rev1 = service.start_plan_run(CAMPAIGN_ID)
    run2, rev2 = service.start_plan_run(CAMPAIGN_ID, prompt="cambia el fondo a algo más vibrante")

    assert run1.status == "succeeded" and run2.status == "succeeded"
    # A fresh plan revision was drafted (number incremented), still status "plan".
    assert rev2 is not None and rev2 != rev1
    assert revisions.rows[rev2]["status"] == "plan"
    assert revisions.rows[rev2]["revision_number"] == revisions.rows[rev1]["revision_number"] + 1


def test_orchestrator_failure_is_recorded_honestly() -> None:
    service, *_ = _build_service()

    class Boom:
        def execute(self, *, run_id: str, campaign_row: dict, **_kwargs):
            raise RuntimeError("pipeline blew up")

    assert service.orchestrator is not None
    service.orchestrator = Boom()  # type: ignore[assignment]

    run = service.start_generation_run(CAMPAIGN_ID)

    assert run.status == "failed"
    assert "pipeline blew up" in (run.error_message or "")


# --- W0.2: multi-product brief + guaranteed chroma -------------------------


def test_multi_product_brief_features_all_products_on_base_variant() -> None:
    """3 products in the brief → the base variant features ALL 3 (not just one)."""
    service, campaigns, revisions, variants, _layouts, _audits = _build_service()
    campaigns.rows[CAMPAIGN_ID]["structured_brief"]["products"] = [
        {"product_title": "Perfume Uno", "product_gid": "gid://shopify/Product/1", "product_image_url": "https://cdn/p1.jpg"},
        {"product_title": "Perfume Dos", "product_gid": "gid://shopify/Product/2", "product_image_url": "https://cdn/p2.jpg"},
        {"product_title": "Perfume Tres", "product_gid": "gid://shopify/Product/3", "product_image_url": "https://cdn/p3.jpg"},
    ]

    run = service.start_generation_run(CAMPAIGN_ID)

    assert run.status == "succeeded"
    revision = next(iter(revisions.rows.values()))
    rows = variants.list_by_revision_id(revision_id=revision["id"])
    rule = rows[0]["audience_rule"]
    featured = rule.get("featured_products") or []
    assert [r["product_title"] for r in featured] == ["Perfume Uno", "Perfume Dos", "Perfume Tres"]
    # Every ref carries its image and an explicit (non-silent) compose status.
    assert all(r.get("product_image_url") for r in featured)
    assert all(r.get("hero_status") for r in featured)
    # Backward-compat single ref points at the primary product.
    assert rule["featured_product"]["product_title"] == "Perfume Uno"


def test_compose_variant_hero_retries_chroma_once_and_reports(monkeypatch) -> None:
    """First gen ignores chroma → ONE reinforced retry; success on retry → ok_retry."""
    import asyncio
    import io

    from PIL import Image

    from app.services.banners import image_gen as image_gen_module
    from app.services.banners.run_orchestrator import _CHROMA_RETRY_PREFIX

    def _png(color) -> bytes:
        img = Image.new("RGB", (64, 64), color)
        # subject: small red square so the keyed PNG keeps some opaque pixels
        for x in range(24, 40):
            for y in range(24, 40):
                img.putpixel((x, y), (200, 30, 30))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    calls: list[str] = []

    async def fake_gen(prompt, **_kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return _png((250, 250, 250)), {"is_real_provider": True}, 0.01  # no chroma field
        return _png((0, 255, 0)), {"is_real_provider": True}, 0.01  # proper chroma green

    monkeypatch.setattr(image_gen_module, "generate_image", fake_gen)

    class _FakeResp:
        status_code = 200
        content = b"jpegbytes"
        headers = {"content-type": "image/jpeg"}

    class _FakeHttp:
        def __init__(self, *a, **k): ...
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def get(self, _url):
            return _FakeResp()

    import httpx

    monkeypatch.setattr(httpx, "Client", _FakeHttp)

    class _Assets:
        def upload_png(self, **kwargs):
            return {"public_url": "https://cdn/hero.png"}

    service, campaigns, revisions, variants, layouts, audits = _build_service()
    orchestrator = service.orchestrator
    orchestrator.asset_service = _Assets()

    class _Concept:
        copy = {"headline": "Promo"}
        layout = "Hero split layout"

    url, status = asyncio.run(
        orchestrator._compose_variant_hero(
            spec={"key": "v1", "product_title": "Perfume", "product_image_url": "https://cdn/p.jpg"},
            concept=_Concept(),
            campaign_id=CAMPAIGN_ID,
            revision_id="rev-1",
        )
    )

    assert url == "https://cdn/hero.png"
    assert status == "ok_retry"
    assert len(calls) == 2
    assert calls[1].startswith(_CHROMA_RETRY_PREFIX)


def test_compose_variant_hero_double_chroma_failure_is_not_silent(monkeypatch) -> None:
    """Both attempts un-keyable → (None, 'chroma_failed'), surfaced in run metadata."""
    import asyncio
    import io

    from PIL import Image

    from app.services.banners import image_gen as image_gen_module

    def _white_png() -> bytes:
        buf = io.BytesIO()
        Image.new("RGB", (64, 64), (250, 250, 250)).save(buf, format="PNG")
        return buf.getvalue()

    async def fake_gen(prompt, **_kwargs):
        return _white_png(), {"is_real_provider": True}, 0.01

    monkeypatch.setattr(image_gen_module, "generate_image", fake_gen)

    class _FakeResp:
        status_code = 200
        content = b"jpegbytes"
        headers = {"content-type": "image/jpeg"}

    class _FakeHttp:
        def __init__(self, *a, **k): ...
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def get(self, _url):
            return _FakeResp()

    import httpx

    monkeypatch.setattr(httpx, "Client", _FakeHttp)

    class _Assets:
        def upload_png(self, **kwargs):
            return {"public_url": "https://cdn/hero.png"}

    service, *_rest = _build_service()
    orchestrator = service.orchestrator
    orchestrator.asset_service = _Assets()

    class _Concept:
        copy = {"headline": "Promo"}
        layout = "Hero split layout"

    url, status = asyncio.run(
        orchestrator._compose_variant_hero(
            spec={"key": "v1", "product_title": "Perfume", "product_image_url": "https://cdn/p.jpg"},
            concept=_Concept(),
            campaign_id=CAMPAIGN_ID,
            revision_id="rev-1",
        )
    )
    assert url is None
    assert status == "chroma_failed"


# --- F4: explicability (decision trace) -------------------------------------


def test_events_and_revision_carry_decision_trace() -> None:
    service, _campaigns, revisions, _variants, _layouts, _audits = _build_service()

    run = service.start_generation_run(CAMPAIGN_ID)

    assert run.status == "succeeded"
    events = service.list_events(run.id)
    draft = next(e for e in events if e.node_key == "draft_banner_concept" and e.status == "succeeded")
    trace = (draft.output_summary or {}).get("decision_trace")
    assert trace and trace.get("decision")
    assert trace.get("reasons"), "reasons must explain layout/copy/brand choices"
    # Deterministic mode is marked honestly (no fabricated LLM provenance).
    assert any("[DETERMINISTIC]" in r for r in trace["reasons"])
    research = next(e for e in events if e.node_key == "research_best_practices" and e.status == "succeeded")
    assert isinstance((research.output_summary or {}).get("sources"), list)
    # The trace is persisted on the revision concept for the canvas.
    revision = next(iter(revisions.rows.values()))
    assert revision["concept"].get("decision_trace", {}).get("decision")


def test_plan_response_exposes_decision_trace() -> None:
    from app.services.banners.revision_service import RevisionService

    service, campaigns, revisions, variants, layouts, _audits = _build_service()

    class _NoRefinements:
        def create(self, *, data):
            return {**data, "id": "rr-1"}
        def get(self, *, refinement_request_id):
            return None
        def update(self, *, refinement_request_id, data):
            return None

    # The shared in-memory repo lacks list_by_campaign_id (only the orchestrator
    # needs it elsewhere) — add it for the plan lookup.
    revisions.list_by_campaign_id = lambda *, campaign_id: [  # type: ignore[attr-defined]
        r for r in revisions.rows.values() if str(r.get("campaign_id")) == campaign_id
    ]
    rev_service = RevisionService(
        campaigns=campaigns, revisions=revisions, variants=variants, layout_variants=layouts,
        refinement_requests=_NoRefinements(), generation_runs=service, team_id="team-1",
    )
    rev_service.start_plan_run(CAMPAIGN_ID)
    plan = rev_service.get_plan(CAMPAIGN_ID)
    assert plan.decision_trace.get("decision")
    assert plan.decision_trace.get("reasons")
