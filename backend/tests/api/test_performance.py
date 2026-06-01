from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.banners.performance_service import PerformanceService
from tests.unit.test_performance_service import (
    CAMPAIGN_ID,
    PROPOSED_REVISION_ID,
    REVISION_ID,
    TEAM_A,
    InMemoryCampaigns,
    InMemoryInsights,
    InMemoryProposals,
    InMemoryRevisions,
    InMemorySnapshots,
)

client = TestClient(app)
AUTH_TEAM_A = {"X-Aijolot-User-Id": "user-a", "X-Aijolot-Team-Id": TEAM_A, "X-Aijolot-Store-Id": "store-a"}
AUTH_TEAM_B = {"X-Aijolot-User-Id": "user-b", "X-Aijolot-Team-Id": "team-b", "X-Aijolot-Store-Id": "store-b"}


def _install(monkeypatch):
    from app.api.v1 import performance

    seen: list[str] = []
    repos = {
        "campaigns": InMemoryCampaigns(),
        "revisions": InMemoryRevisions(),
        "snapshots": InMemorySnapshots(),
        "insights": InMemoryInsights(),
        "proposals": InMemoryProposals(),
    }

    def factory(team_id: str) -> PerformanceService:
        seen.append(team_id)
        return PerformanceService(team_id=team_id, **repos)

    monkeypatch.setattr(performance, "configured_service_for_team", factory)
    return seen


def test_performance_routes_fail_closed_without_context() -> None:
    assert client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/performance").status_code == 401
    assert client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/performance/snapshots", json={"revision_id": REVISION_ID}).status_code == 401
    assert client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/optimization-proposals", json={"source_revision_id": REVISION_ID, "rationale": "x"}).status_code == 401


def test_get_performance_summary_uses_request_team_and_explicit_non_live_message(monkeypatch) -> None:
    seen = _install(monkeypatch)

    response = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/performance", headers=AUTH_TEAM_A)

    assert response.status_code == 200, response.text
    body = response.json()
    assert seen == [TEAM_A]
    assert body["campaign_id"] == CAMPAIGN_ID
    assert body["live_analytics"] is False
    assert "not live analytics" in body["metrics_note"].lower()
    assert [insight["id"] for insight in body["insights"]] == ["insight-team", "insight-campaign"]


def test_post_snapshot_and_proposal_return_created_records(monkeypatch) -> None:
    _install(monkeypatch)

    snapshot = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/performance/snapshots",
        headers=AUTH_TEAM_A,
        json={"revision_id": REVISION_ID, "impressions": 100, "clicks": 10, "conversions": 2, "source": "manual"},
    )
    proposal = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/optimization-proposals",
        headers=AUTH_TEAM_A,
        json={
            "source_revision_id": REVISION_ID,
            "proposed_revision_id": PROPOSED_REVISION_ID,
            "segment_key": "hero",
            "rationale": "V2 mock proposal from manual review.",
            "projected_lift": {"ctr": "+3% mock"},
        },
    )

    assert snapshot.status_code == 200, snapshot.text
    assert snapshot.json()["source"] == "manual"
    assert snapshot.json()["live_analytics"] is False
    assert snapshot.json()["ctr"] == 0.1
    assert proposal.status_code == 200, proposal.text
    assert proposal.json()["status"] == "draft"
    assert proposal.json()["live_analytics"] is False


def test_performance_routes_do_not_leak_cross_team_campaigns(monkeypatch) -> None:
    _install(monkeypatch)

    response = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/performance", headers=AUTH_TEAM_B)

    assert response.status_code == 404
    assert "Short CTA" not in response.text


def test_invalid_snapshot_payload_returns_422(monkeypatch) -> None:
    _install(monkeypatch)

    response = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/performance/snapshots",
        headers=AUTH_TEAM_A,
        json={"revision_id": REVISION_ID, "impressions": 10, "clicks": 1, "ctr": 2},
    )

    assert response.status_code == 422
