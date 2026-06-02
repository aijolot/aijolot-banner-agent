from __future__ import annotations

import copy
from uuid import uuid4

import pytest

from app.schemas.generation import RegenerateRequest
from app.services.banners.generation_run_service import GenerationRunService, InMemoryGenerationEventRepository, InMemoryGenerationRunRepository
from app.services.banners.revision_service import RevisionService, VariantNotFound

CAMPAIGN_ID = "00000000-0000-0000-0000-000000000101"
REVISION_1 = "00000000-0000-0000-0000-000000000201"
REVISION_2 = "00000000-0000-0000-0000-000000000202"
VARIANT_1 = "00000000-0000-0000-0000-000000000301"
VARIANT_2 = "00000000-0000-0000-0000-000000000302"
REFINEMENT_ID = "00000000-0000-0000-0000-000000000401"
USER_ID = "00000000-0000-0000-0000-000000000501"


class InMemoryCampaigns:
    def __init__(self) -> None:
        self.rows = {CAMPAIGN_ID: {"id": CAMPAIGN_ID, "status": "needs_review", "selected_revision_id": REVISION_1}}

    def get(self, *, campaign_id: str, team_id: str | None = None):
        return copy.deepcopy(self.rows.get(campaign_id))

    def update(self, *, campaign_id: str, data: dict, team_id: str | None = None):
        self.rows[campaign_id].update(data)
        return copy.deepcopy(self.rows[campaign_id])


class InMemoryRevisions:
    def __init__(self) -> None:
        self.rows = {
            REVISION_1: {
                "id": REVISION_1,
                "campaign_id": CAMPAIGN_ID,
                "generation_run_id": None,
                "revision_number": 1,
                "status": "selected",
                "concept": {"headline": "Original"},
                "liquid_config": {"section": "hero"},
                "html_preview": "<section>Original</section>",
                "preview_storage_path": None,
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        }

    def create(self, *, data: dict):
        row_id = REVISION_2 if REVISION_2 not in self.rows else str(uuid4())
        row = {"id": row_id, "created_at": "2026-01-01T00:00:01+00:00", **data}
        self.rows[row["id"]] = row
        return copy.deepcopy(row)

    def get(self, *, revision_id: str):
        return copy.deepcopy(self.rows.get(revision_id))

    def get_latest_by_campaign_id(self, *, campaign_id: str):
        rows = [row for row in self.rows.values() if row["campaign_id"] == campaign_id]
        if not rows:
            return None
        return copy.deepcopy(max(rows, key=lambda row: row["revision_number"]))

    def list_by_campaign_id(self, *, campaign_id: str):
        return copy.deepcopy(sorted([row for row in self.rows.values() if row["campaign_id"] == campaign_id], key=lambda r: r["revision_number"]))

    def update(self, *, revision_id: str, data: dict):
        self.rows[revision_id].update(data)
        return copy.deepcopy(self.rows[revision_id])


class InMemoryVariants:
    def __init__(self) -> None:
        self.rows = {
            VARIANT_1: {
                "id": VARIANT_1,
                "revision_id": REVISION_1,
                "segment_key": "default",
                "segment_label": "Default",
                "audience_rule": {},
                "headline": "Original headline",
                "palette": {},
            }
        }
        self.created: list[dict] = []

    def create_many(self, *, variants: list[dict]):
        created = []
        for row in variants:
            new = {"id": VARIANT_2 if not created else str(uuid4()), **row}
            self.rows[new["id"]] = new
            self.created.append(copy.deepcopy(new))
            created.append(copy.deepcopy(new))
        return created

    def get(self, *, variant_id: str):
        return copy.deepcopy(self.rows.get(variant_id))

    def list_by_revision_id(self, *, revision_id: str):
        return copy.deepcopy([row for row in self.rows.values() if row["revision_id"] == revision_id])


class InMemoryLayoutVariants:
    def __init__(self) -> None:
        self.rows = {
            "00000000-0000-0000-0000-000000000601": {
                "id": "00000000-0000-0000-0000-000000000601",
                "revision_id": REVISION_1,
                "key": "A",
                "name": "Layout A",
                "description": "Split",
                "layout_type": "split",
                "is_recommended": True,
                "config": {},
            }
        }

    def create_many(self, *, variants: list[dict]):
        created = []
        for row in variants:
            new = {"id": str(uuid4()), **row}
            self.rows[new["id"]] = new
            created.append(copy.deepcopy(new))
        return created

    def list_by_revision_id(self, *, revision_id: str):
        return copy.deepcopy([row for row in self.rows.values() if row["revision_id"] == revision_id])


class InMemoryRefinements:
    def __init__(self) -> None:
        self.rows = {
            REFINEMENT_ID: {
                "id": REFINEMENT_ID,
                "campaign_id": CAMPAIGN_ID,
                "source_revision_id": REVISION_1,
                "result_revision_id": None,
                "requested_by": USER_ID,
                "prompt": "Make it bolder",
                "status": "queued",
            }
        }

    def create(self, *, data: dict):
        row = {"id": str(uuid4()), **data}
        self.rows[row["id"]] = row
        return copy.deepcopy(row)

    def get(self, *, refinement_request_id: str):
        return copy.deepcopy(self.rows.get(refinement_request_id))

    def update(self, *, refinement_request_id: str, data: dict):
        self.rows[refinement_request_id].update(data)
        return copy.deepcopy(self.rows[refinement_request_id])


@pytest.fixture()
def stack():
    campaigns = InMemoryCampaigns()
    revisions = InMemoryRevisions()
    variants = InMemoryVariants()
    layouts = InMemoryLayoutVariants()
    refinements = InMemoryRefinements()
    generation = GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns,
    )
    service = RevisionService(
        campaigns=campaigns,
        revisions=revisions,
        variants=variants,
        layout_variants=layouts,
        refinement_requests=refinements,
        generation_runs=generation,
    )
    return service, campaigns, revisions, variants, layouts, refinements


def test_select_variant_marks_revision_selected_and_preserves_previous_revisions(stack) -> None:
    service, campaigns, revisions, variants, _layouts, _refinements = stack
    revisions.create(
        data={
            "campaign_id": CAMPAIGN_ID,
            "revision_number": 2,
            "status": "draft",
            "concept": {"headline": "Second"},
            "liquid_config": {},
        }
    )
    variants.create_many(
        variants=[{"revision_id": REVISION_2, "segment_key": "default", "segment_label": "Default", "audience_rule": {}, "palette": {}}]
    )

    response = service.select_variant(CAMPAIGN_ID, VARIANT_2)

    assert response.selected_revision_id == REVISION_2
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == REVISION_2
    assert revisions.rows[REVISION_1]["status"] == "superseded"
    assert revisions.rows[REVISION_2]["status"] == "selected"
    assert len(revisions.rows) == 2


def test_select_variant_rejects_unknown_variant(stack) -> None:
    service, *_ = stack
    with pytest.raises(VariantNotFound):
        service.select_variant(CAMPAIGN_ID, "00000000-0000-0000-0000-000000009999")


def test_regenerate_creates_new_revision_preserves_old_and_updates_refinement(stack) -> None:
    service, campaigns, revisions, variants, layouts, refinements = stack

    response = service.regenerate(CAMPAIGN_ID, RegenerateRequest(refinement_request_id=REFINEMENT_ID))

    assert response.revision.id == REVISION_2
    assert response.revision.revision_number == 2
    assert response.generation_run.run_type == "refinement"
    assert revisions.rows[REVISION_1]["status"] == "superseded"
    assert revisions.rows[REVISION_2]["status"] == "selected"
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == REVISION_2
    assert "Make it bolder" in revisions.rows[REVISION_2]["html_preview"]
    assert refinements.rows[REFINEMENT_ID]["status"] == "succeeded"
    assert refinements.rows[REFINEMENT_ID]["result_revision_id"] == REVISION_2
    assert variants.list_by_revision_id(revision_id=REVISION_1)
    assert variants.list_by_revision_id(revision_id=REVISION_2)
    assert layouts.list_by_revision_id(revision_id=REVISION_1)
    assert layouts.list_by_revision_id(revision_id=REVISION_2)


def test_list_revisions_includes_variants_and_layouts(stack) -> None:
    service, *_ = stack

    revisions = service.list_revisions(CAMPAIGN_ID)

    assert [revision.revision_number for revision in revisions] == [1]
    assert revisions[0].variants[0].id == VARIANT_1
    assert revisions[0].layout_variants[0].key == "A"


def test_regenerate_escapes_prompt_in_html_and_does_not_reuse_preview_path(stack) -> None:
    service, _campaigns, revisions, _variants, _layouts, _refinements = stack
    revisions.rows[REVISION_1]["preview_storage_path"] = "previews/old.html"

    response = service.regenerate(CAMPAIGN_ID, RegenerateRequest(prompt="--><script>alert(1)</script><!--"))
    html_preview = revisions.rows[response.revision.id]["html_preview"]

    assert "<script>alert" not in html_preview
    assert "--><script" not in html_preview
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_preview
    assert revisions.rows[response.revision.id]["preview_storage_path"] is None


def test_regenerate_from_non_selected_source_supersedes_previous_selected_revision(stack) -> None:
    service, campaigns, revisions, _variants, _layouts, _refinements = stack
    selected = revisions.create(
        data={
            "campaign_id": CAMPAIGN_ID,
            "revision_number": 2,
            "status": "selected",
            "concept": {"headline": "Selected"},
            "liquid_config": {},
        }
    )
    revisions.rows[REVISION_1]["status"] = "superseded"
    campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] = selected["id"]

    response = service.regenerate(CAMPAIGN_ID, RegenerateRequest(source_revision_id=REVISION_1, prompt="Try old source"))

    assert revisions.rows[selected["id"]]["status"] == "superseded"
    assert revisions.rows[response.revision.id]["status"] == "selected"
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == response.revision.id
