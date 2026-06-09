from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.banners.generation_run_service import GenerationRunService, InMemoryGenerationEventRepository, InMemoryGenerationRunRepository
from app.services.banners.revision_service import RevisionService
from tests.unit.test_revision_service import (
    CAMPAIGN_ID,
    REFINEMENT_ID,
    REVISION_1,
    REVISION_2,
    VARIANT_1,
    InMemoryCampaigns,
    InMemoryLayoutVariants,
    InMemoryRefinements,
    InMemoryRevisions,
    InMemoryVariants,
)

client = TestClient(app)


def _service() -> tuple[RevisionService, InMemoryCampaigns, InMemoryRevisions, InMemoryVariants, InMemoryRefinements]:
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
    return service, campaigns, revisions, variants, refinements


def test_select_variant_endpoint_updates_campaign_selection(monkeypatch) -> None:
    from app.api.v1 import generation

    service, campaigns, revisions, _variants, _refinements = _service()
    monkeypatch.setattr(generation, "_revision_service", lambda: service)

    response = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/variants/{VARIANT_1}/select")

    assert response.status_code == 200
    body = response.json()
    assert body["selected_revision_id"] == REVISION_1
    assert body["selected_variant_id"] == VARIANT_1
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == REVISION_1
    assert revisions.rows[REVISION_1]["status"] == "selected"


def test_regenerate_endpoint_creates_revision_and_updates_refinement(monkeypatch) -> None:
    from app.api.v1 import generation

    service, campaigns, revisions, _variants, refinements = _service()
    monkeypatch.setattr(generation, "_revision_service", lambda: service)

    response = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/regenerate",
        json={"refinement_request_id": REFINEMENT_ID},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["revision"]["id"] == REVISION_2
    assert body["revision"]["revision_number"] == 2
    assert body["generation_run"]["run_type"] == "refinement"
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == REVISION_2
    assert revisions.rows[REVISION_1]["status"] == "superseded"
    assert refinements.rows[REFINEMENT_ID]["status"] == "succeeded"
    assert refinements.rows[REFINEMENT_ID]["result_revision_id"] == REVISION_2


def test_list_revisions_endpoint_returns_preserved_revisions(monkeypatch) -> None:
    from app.api.v1 import generation

    service, _campaigns, _revisions, _variants, _refinements = _service()
    monkeypatch.setattr(generation, "_revision_service", lambda: service)
    client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/regenerate", json={"prompt": "More urgency"})

    response = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/revisions")

    assert response.status_code == 200
    body = response.json()
    assert [revision["revision_number"] for revision in body] == [1, 2]
    assert body[0]["id"] == REVISION_1
    assert body[1]["id"] == REVISION_2
    assert body[0]["variants"]
    assert body[1]["variants"]


def test_apply_edits_endpoint_creates_revision_without_agent(monkeypatch) -> None:
    from app.api.v1 import generation

    service, campaigns, revisions, _variants, _refinements = _service()
    monkeypatch.setattr(generation, "_revision_service", lambda: service)

    response = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/apply-edits",
        json={"structured_changes": {"layout": {"textX": 30}, "fonts": {"display": "Anton"}}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["revision"]["id"] == REVISION_2
    assert body["generation_run"]["metadata"]["no_agent"] is True
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == REVISION_2
    layout = revisions.rows[REVISION_2]["concept"]["art_direction"]["layout"]
    assert layout["textX"] == 30


def test_apply_edits_endpoint_rejects_unknown_keys(monkeypatch) -> None:
    from app.api.v1 import generation

    service, *_ = _service()
    monkeypatch.setattr(generation, "_revision_service", lambda: service)

    response = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/apply-edits",
        json={"structured_changes": {"layout": {"bogusKey": 1}}},
    )

    assert response.status_code == 422


def test_regenerate_endpoint_404s_for_missing_refinement(monkeypatch) -> None:
    from app.api.v1 import generation

    service, *_ = _service()
    monkeypatch.setattr(generation, "_revision_service", lambda: service)

    response = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/regenerate",
        json={"refinement_request_id": "00000000-0000-0000-0000-000000009999"},
    )

    assert response.status_code == 404
