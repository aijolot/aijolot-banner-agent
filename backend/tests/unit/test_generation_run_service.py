from __future__ import annotations

import pytest

from app.db.repositories.audit_reports import AuditReportRepository
from app.schemas.generation import GenerationRunCreate
from app.services.banners.audit_report_service import deterministic_mvp_audit_report
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
        self.fail_update = False
        self.rows: dict[str, dict] = {}
        self.calls: list[tuple[str, str | None]] = []

    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict | None:
        self.calls.append((campaign_id, team_id))
        if not self.exists:
            return None
        return self.rows.setdefault(
            campaign_id,
            {
                "id": campaign_id,
                "team_id": team_id or "team-1",
                "status": "brief_ready",
                "title": "Black Friday VIP",
                "promo_label": "30% off",
                "raw_brief": "Premium Black Friday hero for VIP customers",
                "structured_brief": {"cta": "Shop now", "audience": "VIP customers"},
                "selected_revision_id": None,
            },
        )

    def update(self, *, campaign_id: str, data: dict, team_id: str | None = None) -> dict | None:
        if self.fail_update:
            return None
        row = self.get(campaign_id=campaign_id, team_id=team_id)
        if row is None:
            return None
        row.update(data)
        return dict(row)


class InMemoryArtifactRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self._sequence = 0

    def create(self, *, data: dict) -> dict:
        self._sequence += 1
        row = {"id": f"00000000-0000-0000-0001-{self._sequence:012d}", "created_at": f"2026-01-01T00:00:00.{self._sequence:06d}+00:00", **data}
        self.rows[row["id"]] = row
        return dict(row)

    def get(self, *, revision_id: str) -> dict | None:
        row = self.rows.get(revision_id)
        return dict(row) if row else None

    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict | None:
        rows = [row for row in self.rows.values() if row.get("campaign_id") == campaign_id]
        if not rows:
            return None
        return dict(max(rows, key=lambda row: int(row.get("revision_number") or 0)))

    def list_by_campaign_id(self, *, campaign_id: str) -> list[dict]:
        return [dict(row) for row in self.rows.values() if row.get("campaign_id") == campaign_id]

    def update(self, *, revision_id: str, data: dict) -> dict | None:
        row = self.rows.get(revision_id)
        if row is None:
            return None
        row.update(data)
        return dict(row)


class InMemoryChildArtifactRepository:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self._sequence = 0

    def create_many(self, *, variants: list[dict]) -> list[dict]:
        created = []
        for variant in variants:
            self._sequence += 1
            row = {"id": f"00000000-0000-0000-0002-{self._sequence:012d}", **variant}
            self.rows.append(row)
            created.append(dict(row))
        return created

    def list_by_revision_id(self, *, revision_id: str) -> list[dict]:
        return [dict(row) for row in self.rows if row.get("revision_id") == revision_id]


class FailingChildArtifactRepository(InMemoryChildArtifactRepository):
    def __init__(self, *, after: int = 0, message: str = "artifact insert failed") -> None:
        super().__init__()
        self.after = after
        self.message = message

    def create_many(self, *, variants: list[dict]) -> list[dict]:
        if self.after <= 0:
            raise RuntimeError(self.message)
        super().create_many(variants=variants[: self.after])
        raise RuntimeError(self.message)


class InMemoryAuditReportRepository(InMemoryArtifactRepository):
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict | None:
        rows = [row for row in self.rows.values() if row.get("campaign_id") == campaign_id]
        return dict(rows[-1]) if rows else None


class FailingAuditReportRepository(InMemoryAuditReportRepository):
    def create(self, *, data: dict) -> dict:
        raise RuntimeError("audit insert failed")


class FailingGenerationEventRepository(InMemoryGenerationEventRepository):
    def create_many(self, *, events: list[dict]) -> list[dict]:
        raise RuntimeError("events insert failed")


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


def test_generation_events_insert_payload_never_has_null_output_summary(service: GenerationRunService) -> None:
    run = service.start_generation_run(CAMPAIGN_ID)

    raw_events = service.event_repository.list_by_run_id(run_id=run.id)  # type: ignore[attr-defined]

    assert raw_events
    assert all("output_summary" in event for event in raw_events)
    assert all(event["output_summary"] is not None for event in raw_events)


def test_latest_run_is_deterministic_most_recent(service: GenerationRunService) -> None:
    first = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(started_by=STARTED_BY_ID))
    second = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(started_by=SECOND_STARTED_BY_ID))

    latest = service.get_latest_for_campaign(CAMPAIGN_ID)

    assert latest.id != first.id
    assert latest.id == second.id
    assert latest.started_by == SECOND_STARTED_BY_ID


def test_start_generation_run_persists_mvp_artifacts_and_selects_new_revision() -> None:
    campaigns = FakeCampaignRepository()
    revisions = InMemoryArtifactRepository()
    layout_variants = InMemoryChildArtifactRepository()
    variants = InMemoryChildArtifactRepository()
    audit_reports = InMemoryAuditReportRepository()
    service = GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns,
        revision_repository=revisions,
        layout_variant_repository=layout_variants,
        variant_repository=variants,
        audit_report_repository=audit_reports,
        team_id="team-1",
    )

    first = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(started_by=STARTED_BY_ID))
    first_revision_id = campaigns.rows[CAMPAIGN_ID]["selected_revision_id"]
    second = service.start_generation_run(CAMPAIGN_ID, GenerationRunCreate(started_by=SECOND_STARTED_BY_ID))
    second_revision_id = campaigns.rows[CAMPAIGN_ID]["selected_revision_id"]

    assert first.id != second.id
    assert first_revision_id != second_revision_id
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "needs_review"
    assert revisions.rows[first_revision_id]["status"] == "superseded"
    assert revisions.rows[second_revision_id]["status"] == "selected"
    assert revisions.rows[second_revision_id]["generation_run_id"] == second.id
    assert revisions.rows[second_revision_id]["revision_number"] == 2
    assert "aijolot-banner" in revisions.rows[second_revision_id]["html_preview"]
    assert [row["key"] for row in layout_variants.list_by_revision_id(revision_id=second_revision_id)] == ["A", "B", "C"]
    assert [row["segment_key"] for row in variants.list_by_revision_id(revision_id=second_revision_id)]
    assert audit_reports.get_latest_by_campaign_id(campaign_id=CAMPAIGN_ID)["revision_id"] == second_revision_id
    audit = audit_reports.get_latest_by_campaign_id(campaign_id=CAMPAIGN_ID)
    assert audit is not None
    assert audit["schema_report"] == {"valid": True}
    assert audit["human_review_required"] is True
    assert audit["avif_skipped"] is True


def test_audit_report_normalization_preserves_deterministic_runtime_fields() -> None:
    payload = deterministic_mvp_audit_report(campaign_id=CAMPAIGN_ID, revision_id="revision-1", generation_run_id="run-1")

    normalized = AuditReportRepository._normalize_for_storage(payload)

    assert normalized["asset_weight_report"]["avif_skipped"] is True
    assert normalized["seo_report"]["audit_runtime"] == {
        "status": "pass",
        "findings": [],
        "schema_report": {"valid": True},
        "human_review_required": True,
        "avif_skipped": True,
    }


def test_artifact_failure_does_not_change_selected_revision() -> None:
    class FailingRevisionRepository(InMemoryArtifactRepository):
        def create(self, *, data: dict) -> dict:
            raise RuntimeError("revision insert failed")

    campaigns = FakeCampaignRepository()
    campaigns.rows[CAMPAIGN_ID] = {"id": CAMPAIGN_ID, "team_id": "team-1", "status": "draft", "selected_revision_id": "existing-revision"}
    service = GenerationRunService(
        run_repository=InMemoryGenerationRunRepository(),
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns,
        revision_repository=FailingRevisionRepository(),
        layout_variant_repository=InMemoryChildArtifactRepository(),
        variant_repository=InMemoryChildArtifactRepository(),
        audit_report_repository=InMemoryAuditReportRepository(),
        team_id="team-1",
    )

    with pytest.raises(RuntimeError, match="revision insert failed"):
        service.start_generation_run(CAMPAIGN_ID)

    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == "existing-revision"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "draft"


def test_layout_variant_partial_failure_keeps_previous_selection_and_marks_run_failed() -> None:
    campaigns = FakeCampaignRepository()
    campaigns.rows[CAMPAIGN_ID] = {"id": CAMPAIGN_ID, "team_id": "team-1", "status": "needs_review", "selected_revision_id": "existing-revision"}
    revisions = InMemoryArtifactRepository()
    revisions.rows["existing-revision"] = {"id": "existing-revision", "campaign_id": CAMPAIGN_ID, "revision_number": 1, "status": "selected"}
    run_repository = InMemoryGenerationRunRepository()
    service = GenerationRunService(
        run_repository=run_repository,
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns,
        revision_repository=revisions,
        layout_variant_repository=FailingChildArtifactRepository(after=1, message="layout variant insert failed"),
        variant_repository=InMemoryChildArtifactRepository(),
        audit_report_repository=InMemoryAuditReportRepository(),
        team_id="team-1",
    )

    with pytest.raises(RuntimeError, match="layout variant insert failed"):
        service.start_generation_run(CAMPAIGN_ID)

    failed_run = run_repository.get_latest_by_campaign_id(campaign_id=CAMPAIGN_ID)
    assert failed_run is not None
    assert failed_run["status"] == "failed"
    assert "layout variant insert failed" in failed_run["error_message"]
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == "existing-revision"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "needs_review"
    assert revisions.rows["existing-revision"]["status"] == "selected"


def test_audit_failure_after_partial_artifacts_keeps_previous_selection_and_marks_run_failed() -> None:
    campaigns = FakeCampaignRepository()
    campaigns.rows[CAMPAIGN_ID] = {"id": CAMPAIGN_ID, "team_id": "team-1", "status": "needs_review", "selected_revision_id": "existing-revision"}
    revisions = InMemoryArtifactRepository()
    revisions.rows["existing-revision"] = {"id": "existing-revision", "campaign_id": CAMPAIGN_ID, "revision_number": 1, "status": "selected"}
    run_repository = InMemoryGenerationRunRepository()
    layout_variants = InMemoryChildArtifactRepository()
    variants = InMemoryChildArtifactRepository()
    service = GenerationRunService(
        run_repository=run_repository,
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns,
        revision_repository=revisions,
        layout_variant_repository=layout_variants,
        variant_repository=variants,
        audit_report_repository=FailingAuditReportRepository(),
        team_id="team-1",
    )

    with pytest.raises(RuntimeError, match="audit insert failed"):
        service.start_generation_run(CAMPAIGN_ID)

    failed_run = run_repository.get_latest_by_campaign_id(campaign_id=CAMPAIGN_ID)
    assert failed_run is not None
    assert failed_run["status"] == "failed"
    assert "audit insert failed" in failed_run["error_message"]
    assert layout_variants.rows
    assert variants.rows
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == "existing-revision"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "needs_review"
    assert revisions.rows["existing-revision"]["status"] == "selected"


def test_campaign_update_failure_does_not_supersede_previous_revision_and_marks_run_failed() -> None:
    campaigns = FakeCampaignRepository()
    campaigns.rows[CAMPAIGN_ID] = {"id": CAMPAIGN_ID, "team_id": "team-1", "status": "needs_review", "selected_revision_id": "existing-revision"}
    campaigns.fail_update = True
    revisions = InMemoryArtifactRepository()
    revisions.rows["existing-revision"] = {"id": "existing-revision", "campaign_id": CAMPAIGN_ID, "revision_number": 1, "status": "selected"}
    run_repository = InMemoryGenerationRunRepository()
    service = GenerationRunService(
        run_repository=run_repository,
        event_repository=InMemoryGenerationEventRepository(),
        campaign_repository=campaigns,
        revision_repository=revisions,
        layout_variant_repository=InMemoryChildArtifactRepository(),
        variant_repository=InMemoryChildArtifactRepository(),
        audit_report_repository=InMemoryAuditReportRepository(),
        team_id="team-1",
    )

    with pytest.raises(RuntimeError, match="campaign update failed"):
        service.start_generation_run(CAMPAIGN_ID)

    failed_run = run_repository.get_latest_by_campaign_id(campaign_id=CAMPAIGN_ID)
    assert failed_run is not None
    assert failed_run["status"] == "failed"
    assert "campaign update failed" in failed_run["error_message"]
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == "existing-revision"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "needs_review"
    selected_revision_ids = [revision_id for revision_id, row in revisions.rows.items() if row.get("status") == "selected"]
    assert selected_revision_ids == ["existing-revision"]


def test_event_insert_failure_happens_before_artifacts_and_marks_run_failed() -> None:
    campaigns = FakeCampaignRepository()
    campaigns.rows[CAMPAIGN_ID] = {"id": CAMPAIGN_ID, "team_id": "team-1", "status": "needs_review", "selected_revision_id": "existing-revision"}
    revisions = InMemoryArtifactRepository()
    revisions.rows["existing-revision"] = {"id": "existing-revision", "campaign_id": CAMPAIGN_ID, "revision_number": 1, "status": "selected"}
    run_repository = InMemoryGenerationRunRepository()
    service = GenerationRunService(
        run_repository=run_repository,
        event_repository=FailingGenerationEventRepository(),
        campaign_repository=campaigns,
        revision_repository=revisions,
        layout_variant_repository=InMemoryChildArtifactRepository(),
        variant_repository=InMemoryChildArtifactRepository(),
        audit_report_repository=InMemoryAuditReportRepository(),
        team_id="team-1",
    )

    with pytest.raises(RuntimeError, match="events insert failed"):
        service.start_generation_run(CAMPAIGN_ID)

    failed_run = run_repository.get_latest_by_campaign_id(campaign_id=CAMPAIGN_ID)
    assert failed_run is not None
    assert failed_run["status"] == "failed"
    assert "events insert failed" in failed_run["error_message"]
    assert campaigns.rows[CAMPAIGN_ID]["selected_revision_id"] == "existing-revision"
    assert revisions.rows == {
        "existing-revision": {"id": "existing-revision", "campaign_id": CAMPAIGN_ID, "revision_number": 1, "status": "selected"}
    }


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
