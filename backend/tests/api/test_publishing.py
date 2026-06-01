from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.unit.test_shopify_publisher import CAMPAIGN_ID, _publisher

client = TestClient(app)


def _install(monkeypatch, *, status: str = "scheduled", target_type: str = "home"):
    from app.api.v1 import publishing

    publisher, fake_client, jobs, campaigns = _publisher(status=status, target_type=target_type)
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

    monkeypatch.setattr(publishing, "_publisher", configured_publisher)
    response = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/publish")

    assert response.status_code == 503
