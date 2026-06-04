from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.unit.test_shopify_publisher import CAMPAIGN_ID, _publisher

client = TestClient(app)


def _install(monkeypatch, *, status: str = "scheduled", target_type: str = "home", publish_mode: str = "live"):
    from app.api.v1 import publishing

    publisher, fake_client, jobs, campaigns = _publisher(status=status, target_type=target_type, publish_mode=publish_mode)
    monkeypatch.setattr(publishing, "_publisher", lambda: publisher)
    return publisher, fake_client, jobs, campaigns


def test_publish_and_unpublish_campaign(monkeypatch) -> None:
    _, fake_client, jobs, campaigns = _install(monkeypatch)

    published = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/publish")
    unpublished = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/unpublish")

    assert published.status_code == 200, published.text
    assert published.json()["status"] == "succeeded"
    assert published.json()["action"] == "publish"
    assert campaigns.rows[CAMPAIGN_ID]["status"] == "approved"
    assert fake_client.calls[0][0] == "put_asset"
    assert any(call[0] == "put_metafield" for call in fake_client.calls)
    assert unpublished.status_code == 200, unpublished.text
    assert unpublished.json()["action"] == "unpublish"
    assert jobs.created[-1]["action"] == "unpublish"


def test_publish_endpoint_can_return_safe_dry_run_preview(monkeypatch) -> None:
    _, fake_client, jobs, _ = _install(monkeypatch, publish_mode="dry_run_demo")

    response = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/publish")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["action"] == "publish"
    assert body["response_payload"]["mode"] == "dry_run_demo"
    assert body["response_payload"]["live_shopify_mutation"] is False
    assert body["response_payload"]["theme_files"][0]["key"] == "sections/aijolot-banner-agent.liquid"
    assert body["response_payload"]["metafield"]["key"] == "banner_campaigns"
    assert fake_client.calls == []
    assert jobs.created[-1]["request_payload"]["publish_mode"] == "dry_run_demo"


def test_publish_endpoint_enforces_approval_and_unsupported_search(monkeypatch) -> None:
    _install(monkeypatch, status="needs_review")
    denied = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/publish")
    assert denied.status_code == 409

    _install(monkeypatch, target_type="search")
    unsupported = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/publish")
    assert unsupported.status_code == 422
    assert "search result placement" in unsupported.json()["detail"]


def test_default_publishing_endpoint_returns_503(monkeypatch) -> None:
    from app.api.v1 import publishing
    from app.services.shopify.publisher import configured_publisher

    monkeypatch.delenv("AIJOLOT_PUBLISH_MODE", raising=False)
    monkeypatch.setattr(publishing, "_publisher", configured_publisher)
    response = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/publish")

    assert response.status_code == 503


def test_default_publishing_uses_request_team_context(monkeypatch) -> None:
    from app.api.v1 import publishing

    captured = {}
    publisher, _fake_client, _jobs, _campaigns = _publisher(publish_mode="dry_run_demo")

    def fake_configured_publisher(*, team_id: str | None = None):
        captured["team_id"] = team_id
        return publisher

    monkeypatch.setattr(publishing, "_publisher", publishing._DEFAULT_PUBLISHER_FACTORY)
    monkeypatch.setattr(publishing, "configured_publisher", fake_configured_publisher)

    response = client.post(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/publish",
        headers={"x-aijolot-user-id": "00000000-0000-0000-0000-000000000101", "x-aijolot-team-id": "00000000-0000-0000-0000-000000000001"},
    )

    assert response.status_code == 200, response.text
    assert captured["team_id"] == "00000000-0000-0000-0000-000000000001"


def test_default_publishing_requires_request_context(monkeypatch) -> None:
    from app.api.v1 import publishing

    monkeypatch.setattr(publishing, "_publisher", publishing._DEFAULT_PUBLISHER_FACTORY)

    response = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/publish")

    assert response.status_code == 401
