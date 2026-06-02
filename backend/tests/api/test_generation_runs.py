from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.generation import GenerationEventResponse, GenerationRunCreate, GenerationRunResponse

client = TestClient(app)
CAMPAIGN_ID = "00000000-0000-0000-0000-000000000401"
UNKNOWN_CAMPAIGN_ID = "00000000-0000-0000-0000-000000000999"
RUN_ID = "00000000-0000-0000-0000-000000000501"
UNKNOWN_RUN_ID = "00000000-0000-0000-0000-000000000599"
STARTED_BY_ID = "00000000-0000-0000-0000-000000000601"


class FakeGenerationRunService:
    def __init__(self) -> None:
        self.run: GenerationRunResponse | None = None
        self.events: list[GenerationEventResponse] = []

    def start_generation_run(self, campaign_id: str, request: GenerationRunCreate | None = None):
        if campaign_id == UNKNOWN_CAMPAIGN_ID:
            from app.services.banners.generation_run_service import CampaignNotFound

            raise CampaignNotFound(campaign_id)
        self.run = GenerationRunResponse(
            id=RUN_ID,
            campaign_id=campaign_id,
            run_type=(request.run_type if request else "initial"),
            status="succeeded",
            frontend_step="review_publish",
            adk_trace_id="trace-1",
            started_by=(request.started_by if request else None),
            metadata={"facade_version": "task-10-deterministic", **((request.metadata if request else {}) or {})},
        )
        self.events = [
            GenerationEventResponse(
                id="event-1",
                generation_run_id=RUN_ID,
                node_key="load_brand_context",
                frontend_step="intake_context",
                status="started",
            ),
            GenerationEventResponse(
                id="event-2",
                generation_run_id=RUN_ID,
                node_key="publish_to_shopify",
                frontend_step="review_publish",
                status="succeeded",
            ),
        ]
        return self.run

    def get_latest_for_campaign(self, campaign_id: str):
        if campaign_id == UNKNOWN_CAMPAIGN_ID:
            from app.services.banners.generation_run_service import CampaignNotFound

            raise CampaignNotFound(campaign_id)
        if self.run and self.run.campaign_id == campaign_id:
            return self.run
        from app.services.banners.generation_run_service import CampaignGenerationRunNotFound

        raise CampaignGenerationRunNotFound(campaign_id)

    def get_run(self, run_id: str):
        if self.run and self.run.id == run_id:
            return self.run
        from app.services.banners.generation_run_service import GenerationRunNotFound

        raise GenerationRunNotFound(run_id)

    def list_events(self, run_id: str):
        if self.run and self.run.id == run_id:
            return self.events
        from app.services.banners.generation_run_service import GenerationRunNotFound

        raise GenerationRunNotFound(run_id)


def test_start_get_latest_get_run_and_list_events(monkeypatch) -> None:
    from app.api.v1 import generation

    fake = FakeGenerationRunService()
    monkeypatch.setattr(generation, "_default_service", lambda: fake)

    post = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/generation-runs",
        json={"started_by": STARTED_BY_ID, "metadata": {"source": "api-test"}},
    )
    latest = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/generation-runs/latest")
    run = client.get(f"/api/v1/generation-runs/{RUN_ID}")
    events = client.get(f"/api/v1/generation-runs/{RUN_ID}/events")

    assert post.status_code == 200
    assert post.json()["id"] == RUN_ID
    assert post.json()["campaign_id"] == CAMPAIGN_ID
    assert post.json()["status"] == "succeeded"
    assert post.json()["frontend_step"] == "review_publish"
    assert post.json()["started_by"] == STARTED_BY_ID
    assert post.json()["metadata"]["source"] == "api-test"
    assert latest.status_code == 200
    assert latest.json()["id"] == RUN_ID
    assert run.status_code == 200
    assert run.json()["adk_trace_id"] == "trace-1"
    assert events.status_code == 200
    assert [(event["node_key"], event["frontend_step"], event["status"]) for event in events.json()] == [
        ("load_brand_context", "intake_context", "started"),
        ("publish_to_shopify", "review_publish", "succeeded"),
    ]


def test_post_unknown_campaign_returns_404(monkeypatch) -> None:
    from app.api.v1 import generation

    monkeypatch.setattr(generation, "_default_service", lambda: FakeGenerationRunService())

    response = client.post(f"/api/v1/campaigns/{UNKNOWN_CAMPAIGN_ID}/generation-runs", json={})

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_latest_missing_campaign_or_run_returns_404(monkeypatch) -> None:
    from app.api.v1 import generation

    monkeypatch.setattr(generation, "_default_service", lambda: FakeGenerationRunService())

    missing_campaign = client.get(f"/api/v1/campaigns/{UNKNOWN_CAMPAIGN_ID}/generation-runs/latest")
    missing_latest = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/generation-runs/latest")

    assert missing_campaign.status_code == 404
    assert missing_latest.status_code == 404
    assert "generation run" in missing_latest.json()["detail"]


def test_missing_run_and_events_return_404(monkeypatch) -> None:
    from app.api.v1 import generation

    monkeypatch.setattr(generation, "_default_service", lambda: FakeGenerationRunService())

    run = client.get(f"/api/v1/generation-runs/{UNKNOWN_RUN_ID}")
    events = client.get(f"/api/v1/generation-runs/{UNKNOWN_RUN_ID}/events")

    assert run.status_code == 404
    assert events.status_code == 404
    assert "generation run" in run.json()["detail"]
    assert "generation run" in events.json()["detail"]


def test_invalid_uuids_and_body_return_422(monkeypatch) -> None:
    from app.api.v1 import generation

    monkeypatch.setattr(generation, "_default_service", lambda: FakeGenerationRunService())

    assert client.post("/api/v1/campaigns/not-a-uuid/generation-runs", json={}).status_code == 422
    assert client.get("/api/v1/campaigns/not-a-uuid/generation-runs/latest").status_code == 422
    assert client.get("/api/v1/generation-runs/not-a-uuid").status_code == 422
    assert client.get("/api/v1/generation-runs/not-a-uuid/events").status_code == 422
    invalid_body = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/generation-runs",
        json={"run_type": "bad"},
    )
    assert invalid_body.status_code == 422
    invalid_started_by = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/generation-runs",
        json={"started_by": "not-a-uuid"},
    )
    assert invalid_started_by.status_code == 422
