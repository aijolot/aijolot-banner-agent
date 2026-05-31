from __future__ import annotations

import pytest

from app.schemas.generation import GenerationRunCreate
from app.services.banners.generation_run_service import (
    CampaignGenerationRunNotFound,
    CampaignNotFound,
    GenerationRunNotFound,
    GenerationRunService,
    InMemoryGenerationEventRepository,
    InMemoryGenerationRunRepository,
)
from app.workflows.banner_creation import FRONTEND_PROGRESS_STEPS, frontend_step_for_node, ordered_node_keys

CAMPAIGN_ID = "00000000-0000-0000-0000-000000000401"
STARTED_BY_ID = "00000000-0000-0000-0000-000000000601"
SECOND_STARTED_BY_ID = "00000000-0000-0000-0000-000000000602"


class FakeCampaignRepository:
    def __init__(self, *, exists: bool = True) -> None:
        self.exists = exists
        self.calls: list[tuple[str, str | None]] = []

    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict | None:
        self.calls.append((campaign_id, team_id))
        if not self.exists:
            return None
        return {"id": campaign_id, "team_id": team_id or "team-1", "status": "brief_ready"}


@pytest.fixture
def service() -> GenerationRunService:
    return GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=FakeCampaignRepository(),
        team_id="team-1",
    )


def test_frontend_facade_maps_all_twelve_nodes_in_order() -> None:
    assert [step["key"] for step in FRONTEND_PROGRESS_STEPS] == [
        "intake_context",
        "concept",
        "image",
        "render_audit",
        "review_publish",
    ]
    assert ordered_node_keys() == [
        "load_brand_context",
        "intake_campaign_idea",
        "capture_user_personalization",
        "research_best_practices",
        "draft_banner_concept",
        "generate_image",
        "optimize_assets",
        "render_html",
        "audit",
        "human_review",
        "schedule_or_publish",
        "publish_to_shopify",
    ]
    assert [frontend_step_for_node(node) for node in ordered_node_keys()] == [
        "intake_context",
        "intake_context",
        "intake_context",
        "intake_context",
        "concept",
        "image",
        "image",
        "render_audit",
        "render_audit",
        "review_publish",
        "review_publish",
        "review_publish",
    ]


def test_start_generation_run_creates_succeeded_run_and_deterministic_events(service: GenerationRunService) -> None:
    run = service.start_generation_run(
        CAMPAIGN_ID,
        GenerationRunCreate(started_by=STARTED_BY_ID, metadata={"source": "test"}),
    )
    events = service.list_events(run.id)

    assert run.campaign_id == CAMPAIGN_ID
    assert run.status == "succeeded"
    assert run.frontend_step == "review_publish"
    assert run.started_by == STARTED_BY_ID
    assert run.metadata["facade_version"] == "task-10-deterministic"
    assert run.metadata["source"] == "test"
    assert [step.key for step in run.progress] == ["intake_context", "concept", "image", "render_audit", "review_publish"]
    assert all(step.status == "succeeded" for step in run.progress)
    assert len(events) == 24
    assert [(event.node_key, event.status, event.frontend_step) for event in events[:4]] == [
        ("load_brand_context", "started", "intake_context"),
        ("load_brand_context", "succeeded", "intake_context"),
        ("intake_campaign_idea", "started", "intake_context"),
        ("intake_campaign_idea", "succeeded", "intake_context"),
    ]
    assert events[-1].node_key == "publish_to_shopify"
    assert events[-1].frontend_step == "review_publish"
    assert events[-1].status == "succeeded"
    assert events[0].input_summary == {"summary": "Deterministic Task 10 input for load_brand_context"}
    assert events[1].output_summary == {"summary": "Deterministic Task 10 output for load_brand_context"}
    assert [event.created_at for event in events] == sorted(event.created_at for event in events if event.created_at)
    assert len({event.created_at for event in events}) == len(events)


def test_latest_run_is_deterministic_most_recent(service: GenerationRunService) -> None:
    first = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(started_by=STARTED_BY_ID))
    second = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(started_by=SECOND_STARTED_BY_ID))

    latest = service.get_latest_for_campaign(CAMPAIGN_ID)

    assert latest.id != first.id
    assert latest.id == second.id
    assert latest.started_by == SECOND_STARTED_BY_ID


def test_parent_run_must_exist_and_match_campaign(service: GenerationRunService) -> None:
    parent = service.start_generation_run(CAMPAIGN_ID)
    child = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(parent_run_id=parent.id))

    assert child.parent_run_id == parent.id

    with pytest.raises(GenerationRunNotFound):
        service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(parent_run_id="00000000-0000-0000-0000-000000000999"))

    other_campaign = "00000000-0000-0000-0000-000000000402"
    other_parent = service.start_generation_run(other_campaign)
    with pytest.raises(GenerationRunNotFound):
        service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(parent_run_id=other_parent.id))


def test_request_metadata_cannot_override_internal_facade_version(service: GenerationRunService) -> None:
    run = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(metadata={"facade_version": "client", "source": "test"}))

    assert run.metadata["facade_version"] == "task-10-deterministic"
    assert run.metadata["source"] == "test"


def test_missing_campaign_raises_when_repository_configured() -> None:
    service = GenerationRunService(campaign_repository=FakeCampaignRepository(exists=False))

    with pytest.raises(CampaignNotFound):
        service.start_generation_run(CAMPAIGN_ID)
    with pytest.raises(CampaignNotFound):
        service.get_latest_for_campaign(CAMPAIGN_ID)


def test_get_run_and_list_events_verify_run_campaign_scope() -> None:
    campaign_repository = FakeCampaignRepository(exists=True)
    service = GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaign_repository,
        team_id="team-1",
    )
    run = service.start_generation_run(CAMPAIGN_ID)

    campaign_repository.calls.clear()

    assert service.get_run(run.id).id == run.id
    assert service.list_events(run.id)
    assert campaign_repository.calls == [(CAMPAIGN_ID, "team-1"), (CAMPAIGN_ID, "team-1")]


def test_get_run_and_list_events_raise_when_run_campaign_not_in_team() -> None:
    run_repository = InMemoryGenerationRunRepository()
    event_repository = InMemoryGenerationEventRepository()
    creating_service = GenerationRunService(run_repository=run_repository, event_repository=event_repository)
    run = creating_service.start_generation_run(CAMPAIGN_ID)
    scoped_service = GenerationRunService(
        run_repository=run_repository,
        event_repository=event_repository,
        campaign_repository=FakeCampaignRepository(exists=False),
        team_id="team-1",
    )

    with pytest.raises(CampaignNotFound):
        scoped_service.get_run(run.id)
    with pytest.raises(CampaignNotFound):
        scoped_service.list_events(run.id)


def test_supabase_jsonb_empty_summaries_serialize() -> None:
    event = GenerationRunService._event_response_from_record(
        {
            "id": "event-1",
            "generation_run_id": "run-1",
            "node_key": "load_brand_context",
            "frontend_step": "intake_context",
            "status": "started",
            "input_summary": {},
            "output_summary": {},
            "duration_ms": None,
            "cost_usd": None,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )

    assert event.input_summary == {}
    assert event.output_summary == {}


def test_missing_run_and_latest_raise(service: GenerationRunService) -> None:
    missing_run_id = "00000000-0000-0000-0000-000000000999"

    with pytest.raises(CampaignGenerationRunNotFound):
        service.get_latest_for_campaign(CAMPAIGN_ID)
    with pytest.raises(GenerationRunNotFound):
        service.get_run(missing_run_id)
    with pytest.raises(GenerationRunNotFound):
        service.list_events(missing_run_id)


def test_local_mode_allows_unconfigured_campaign_repository() -> None:
    service = GenerationRunService()

    run = service.start_generation_run(CAMPAIGN_ID)

    assert run.campaign_id == CAMPAIGN_ID
    assert service.get_run(run.id).id == run.id
