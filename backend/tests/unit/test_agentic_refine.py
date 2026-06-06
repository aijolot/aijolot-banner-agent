"""F9 — agentic refine: target routing + orchestrator refine + regenerate wiring."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.generation import RegenerateRequest
from app.services.banners.generation_run_service import (
    GenerationRunService,
    InMemoryGenerationEventRepository,
    InMemoryGenerationRunRepository,
)
from app.services.banners.revision_service import RevisionService
from app.services.banners.run_orchestrator import RunOrchestrator

SKILLS = Path(__file__).resolve().parents[2] / "app" / "agents" / "skills"
CAMPAIGN_ID = "00000000-0000-0000-0000-000000000401"


def _load_skill(skill_id: str) -> Any:
    path = SKILLS / skill_id / "impl.py"
    spec = importlib.util.spec_from_file_location(f"test_{skill_id.replace('-', '_')}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- target routing --------------------------------------------------------


def test_route_classifies_keywords() -> None:
    route = _load_skill("refinement-route")
    assert route.route("haz el copy más urgente y cambia el fondo") == ["copy", "background"]
    assert route.route("nueva imagen del producto") == ["image"]
    assert route.route("ajusta el layout y la estructura") == ["layout"]
    assert route.route("algo distinto") == ["concept", "copy"]  # default


def test_normalize_targets_prefers_explicit() -> None:
    route = _load_skill("refinement-route")
    assert route.normalize_targets(["background", "bogus"], "whatever") == ["background"]
    assert route.normalize_targets(None, "cambia el fondo") == ["background"]
    assert route.normalize_targets([], "make copy punchier") == ["copy"]


# --- in-memory stack -------------------------------------------------------


class InMemoryCampaigns:
    def __init__(self) -> None:
        self.rows = {
            CAMPAIGN_ID: {
                "id": CAMPAIGN_ID,
                "team_id": "team-1",
                "title": "Promo",
                "status": "needs_review",
                "selected_revision_id": None,
                "structured_brief": {"goal": "Promo", "audience": "all", "cta": "Shop", "tone": "bold", "urgency": "high", "placement": "hero_main"},
            }
        }

    def get(self, *, campaign_id, team_id=None):
        return copy.deepcopy(self.rows.get(campaign_id))

    def update(self, *, campaign_id, data, team_id=None):
        self.rows[campaign_id].update(data)
        return copy.deepcopy(self.rows[campaign_id])


class InMemoryRevisions:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def create(self, *, data):
        row = {"id": str(uuid4()), "created_at": "2026-01-01T00:00:00+00:00", **data}
        self.rows[row["id"]] = row
        return copy.deepcopy(row)

    def get(self, *, revision_id):
        return copy.deepcopy(self.rows.get(revision_id))

    def get_latest_by_campaign_id(self, *, campaign_id):
        rows = [r for r in self.rows.values() if r["campaign_id"] == campaign_id]
        return copy.deepcopy(max(rows, key=lambda r: r["revision_number"])) if rows else None

    def list_by_campaign_id(self, *, campaign_id):
        return copy.deepcopy(sorted([r for r in self.rows.values() if r["campaign_id"] == campaign_id], key=lambda r: r["revision_number"]))

    def update(self, *, revision_id, data):
        self.rows[revision_id].update(data)
        return copy.deepcopy(self.rows[revision_id])


class InMemoryVariants:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def create_many(self, *, variants):
        out = []
        for row in variants:
            new = {"id": str(uuid4()), **row}
            self.rows[new["id"]] = new
            out.append(copy.deepcopy(new))
        return out

    def list_by_revision_id(self, *, revision_id):
        return copy.deepcopy([r for r in self.rows.values() if r["revision_id"] == revision_id])


class InMemoryAudits:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def create(self, *, data):
        self.rows.append(dict(data))
        return dict(data)


class InMemoryRefinements:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def create(self, *, data):
        row = {"id": str(uuid4()), **data}
        self.rows[row["id"]] = row
        return dict(row)

    def get(self, *, refinement_request_id):
        return self.rows.get(refinement_request_id)

    def update(self, *, refinement_request_id, data):
        self.rows[refinement_request_id].update(data)
        return self.rows[refinement_request_id]


def _build_stack():
    campaigns = InMemoryCampaigns()
    revisions = InMemoryRevisions()
    variants = InMemoryVariants()
    layouts = InMemoryVariants()
    audits = InMemoryAudits()
    refinements = InMemoryRefinements()
    orchestrator = RunOrchestrator(
        revisions=revisions, variants=variants, layout_variants=layouts,
        audit_reports=audits, campaigns=campaigns, asset_service=None, team_id="team-1",
    )
    gen = GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns,
        orchestrator=orchestrator,
        team_id="team-1",
    )
    svc = RevisionService(
        campaigns=campaigns, revisions=revisions, variants=variants, layout_variants=layouts,
        refinement_requests=refinements, generation_runs=gen, team_id="team-1",
    )
    return svc, campaigns, revisions


def test_banner_edit_scoped_creates_new_revision_and_supersedes() -> None:
    svc, campaigns, revisions = _build_stack()
    svc.generation_runs.start_generation_run(CAMPAIGN_ID)
    initial = revisions.get_latest_by_campaign_id(campaign_id=CAMPAIGN_ID)

    # Background-only edit: new revision, background attached, copy preserved.
    result = svc.edit(CAMPAIGN_ID, RegenerateRequest(prompt="cambia el fondo a algo más oscuro", target_nodes=["background"]))

    assert result.generation_run.status == "succeeded"
    assert result.generation_run.metadata["facade_version"] == "f-banner-edit"
    assert result.generation_run.metadata.get("edit_targets") == ["background"]
    new_rev = revisions.get(revision_id=result.revision.id)
    assert new_rev["revision_number"] > initial["revision_number"]
    assert new_rev["status"] == "selected"
    assert new_rev["html_preview"] and "<" in new_rev["html_preview"]
    assert new_rev["concept"].get("background", {}).get("css")
    # source superseded, campaign points at the edit
    assert revisions.get(revision_id=initial["id"])["status"] == "superseded"
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == new_rev["id"]


def test_agentic_regenerate_creates_real_new_revision() -> None:
    svc, campaigns, revisions = _build_stack()

    # Seed an initial revision via the orchestrator (initial run).
    svc.generation_runs.start_generation_run(CAMPAIGN_ID)
    initial = revisions.get_latest_by_campaign_id(campaign_id=CAMPAIGN_ID)
    assert initial and initial["status"] == "selected"

    result = svc.regenerate(CAMPAIGN_ID, RegenerateRequest(prompt="haz el copy más urgente y cambia el fondo"))

    assert result.generation_run.status == "succeeded"
    assert result.generation_run.run_type == "refinement"
    assert result.generation_run.metadata["facade_version"] == "f9-refine-orchestrator"
    # A genuinely new revision (not a copy) was created and selected.
    new_rev = revisions.get(revision_id=result.revision.id)
    assert new_rev["revision_number"] > initial["revision_number"]
    assert new_rev["status"] == "selected"
    assert new_rev["html_preview"] and "<" in new_rev["html_preview"]
    # Refinement note + AI background recorded on the concept.
    assert new_rev["concept"].get("copy", {}).get("revision_note")
    assert new_rev["concept"].get("background", {}).get("css")
    # Campaign points at the new revision; old one superseded.
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == new_rev["id"]
    assert revisions.get(revision_id=initial["id"])["status"] == "superseded"
