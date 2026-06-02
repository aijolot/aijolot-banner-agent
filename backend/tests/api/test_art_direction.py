from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.art_direction import ArtDirectionResponse

client = TestClient(app)
CAMPAIGN_ID = "00000000-0000-0000-0000-000000000301"
UNKNOWN_CAMPAIGN_ID = "00000000-0000-0000-0000-000000000999"
AUTH_HEADERS = {"X-Aijolot-User-Id": "test-user", "X-Aijolot-Team-Id": "test-team", "X-Aijolot-Store-Id": "test-store"}


class FakeArtDirectionService:
    def __init__(self) -> None:
        self.saved: ArtDirectionResponse | None = None

    def save_art_direction(self, campaign_id: str, request):
        if campaign_id == UNKNOWN_CAMPAIGN_ID:
            from app.services.banners.art_direction_service import CampaignNotFound

            raise CampaignNotFound(campaign_id)
        self.saved = ArtDirectionResponse(
            id="art-direction-1",
            campaign_id=campaign_id,
            **request.model_dump(),
        )
        return self.saved

    def get_art_direction(self, campaign_id: str):
        if self.saved and self.saved.campaign_id == campaign_id:
            return self.saved
        from app.services.banners.art_direction_service import ArtDirectionNotFound

        raise ArtDirectionNotFound(campaign_id)


def test_put_and_get_campaign_art_direction(monkeypatch) -> None:
    from app.api.v1 import art_direction

    fake = FakeArtDirectionService()
    monkeypatch.setattr(art_direction, "_default_service", lambda: fake)

    payload = {
        "background_mode": "hero",
        "hero_style_key": "luxury-gradient",
        "model_key": "seed-model",
        "custom_model": {"persona": "metadata-only"},
        "fold_percentage": 60,
        "layout_hints": {"safe_zone": "left"},
    }
    put = client.put(f"/api/v1/campaigns/{CAMPAIGN_ID}/art-direction", headers=AUTH_HEADERS, json=payload)
    get = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/art-direction", headers=AUTH_HEADERS)

    assert put.status_code == 200
    assert put.json()["campaign_id"] == CAMPAIGN_ID
    assert put.json()["background_mode"] == "hero"
    assert put.json()["custom_model"] == {"persona": "metadata-only"}
    assert get.status_code == 200
    assert get.json()["id"] == "art-direction-1"
    assert get.json()["layout_hints"] == {"safe_zone": "left"}


def test_put_unknown_campaign_returns_404(monkeypatch) -> None:
    from app.api.v1 import art_direction

    monkeypatch.setattr(art_direction, "_default_service", lambda: FakeArtDirectionService())

    response = client.put(
        f"/api/v1/campaigns/{UNKNOWN_CAMPAIGN_ID}/art-direction",
        headers=AUTH_HEADERS,
        json={"background_mode": "usage"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_missing_art_direction_returns_404(monkeypatch) -> None:
    from app.api.v1 import art_direction

    monkeypatch.setattr(art_direction, "_default_service", lambda: FakeArtDirectionService())

    response = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/art-direction", headers=AUTH_HEADERS)

    assert response.status_code == 404
    assert "art direction" in response.json()["detail"]


def test_invalid_art_direction_body_returns_422(monkeypatch) -> None:
    from app.api.v1 import art_direction

    monkeypatch.setattr(art_direction, "_default_service", lambda: FakeArtDirectionService())

    invalid_mode = client.put(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/art-direction",
        json={"background_mode": "invalid"},
    )
    invalid_fold = client.put(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/art-direction",
        json={"background_mode": "hero", "fold_percentage": -1},
    )
    invalid_custom_model = client.put(
        f"/api/v1/campaigns/{CAMPAIGN_ID}/art-direction",
        json={"background_mode": "hero", "custom_model": []},
    )

    assert invalid_mode.status_code == 422
    assert invalid_fold.status_code == 422
    assert invalid_custom_model.status_code == 422


def test_invalid_campaign_uuid_returns_422(monkeypatch) -> None:
    from app.api.v1 import art_direction

    monkeypatch.setattr(art_direction, "_default_service", lambda: FakeArtDirectionService())

    assert client.get("/api/v1/campaigns/not-a-uuid/art-direction").status_code == 422
    assert client.put("/api/v1/campaigns/not-a-uuid/art-direction", json={"background_mode": "hero"}).status_code == 422
