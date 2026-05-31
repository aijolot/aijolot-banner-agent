from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.placements import CampaignPlacementResponse, PlacementTargetMap, PlacementTypeSummary, PlacementValidationResponse

client = TestClient(app)
STORE_ID = "00000000-0000-0000-0000-000000000101"
CAMPAIGN_ID = "00000000-0000-0000-0000-000000000301"


class FakePlacementService:
    def __init__(self) -> None:
        self.saved: CampaignPlacementResponse | None = None

    def list_placement_types(self, store_id: str):
        if store_id != STORE_ID:
            from app.services.shopify.resource_service import StoreNotFound

            raise StoreNotFound(store_id)
        return [
            PlacementTypeSummary(
                id="pt-hero",
                key="hero_main",
                label="Hero principal",
                description="Primary hero",
                supported_targets=["home", "collection", "page"],
                supported_slots=[{"key": "hero", "label": "Hero principal"}],
                default_dimensions={"desktop": {"width": 1440, "height": 420}},
                config_schema={},
                is_active=True,
            )
        ]

    def list_targets(self, store_id: str, placement_type_key: str):
        if placement_type_key != "hero_main":
            from app.services.banners.placement_service import PlacementTypeNotFound

            raise PlacementTypeNotFound(placement_type_key)
        return PlacementTargetMap(
            root={"home": [], "collection": []},
            home=[],
            collection=[],
            product=[],
            page=[],
            search=[],
            store=[],
        )

    def validate(self, request):
        if request.placement_type_key == "bad":
            from app.services.banners.placement_service import InvalidPlacement

            raise InvalidPlacement("invalid placement")
        return PlacementValidationResponse(valid=True, placement=request.to_normalized(placement_type_id="pt-hero"), errors=[])

    def save_campaign_placement(self, campaign_id: str, request):
        if campaign_id.endswith("999"):
            from app.services.banners.placement_service import CampaignNotFound

            raise CampaignNotFound(campaign_id)
        normalized = request.to_normalized(placement_type_id="pt-hero")
        self.saved = CampaignPlacementResponse(
            id="placement-1",
            campaign_id=campaign_id,
            placement_type_id="pt-hero",
            placement_type_key=request.placement_type_key,
            **normalized.model_dump(exclude={"placement_type_id", "placement_type_key"}),
        )
        return self.saved

    def get_campaign_placement(self, campaign_id: str):
        if self.saved and self.saved.campaign_id == campaign_id:
            return self.saved
        from app.services.banners.placement_service import CampaignPlacementNotFound

        raise CampaignPlacementNotFound(campaign_id)


def test_list_placement_types(monkeypatch) -> None:
    from app.api.v1 import placements

    monkeypatch.setattr(placements, "_default_service", lambda: FakePlacementService())

    response = client.get(f"/api/v1/stores/{STORE_ID}/placement-types")

    assert response.status_code == 200
    assert response.json()[0]["key"] == "hero_main"


def test_list_placement_targets(monkeypatch) -> None:
    from app.api.v1 import placements

    monkeypatch.setattr(placements, "_default_service", lambda: FakePlacementService())

    response = client.get(f"/api/v1/stores/{STORE_ID}/placement-types/hero_main/targets")

    assert response.status_code == 200
    assert "collection" in response.json()


def test_validate_placement(monkeypatch) -> None:
    from app.api.v1 import placements

    monkeypatch.setattr(placements, "_default_service", lambda: FakePlacementService())

    response = client.post(
        "/api/v1/placements/validate",
        json={
            "store_id": STORE_ID,
            "placement_type_key": "hero_main",
            "mode": "new_section",
            "target_type": "home",
            "layout_json": {"cols": [{"rows": 1, "w": 1, "align": "center"}]},
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["placement"]["target_type"] == "home"


def test_validate_invalid_placement_returns_400(monkeypatch) -> None:
    from app.api.v1 import placements

    monkeypatch.setattr(placements, "_default_service", lambda: FakePlacementService())

    response = client.post(
        "/api/v1/placements/validate",
        json={"store_id": STORE_ID, "placement_type_key": "bad", "mode": "new_section", "target_type": "home"},
    )

    assert response.status_code == 400


def test_save_and_get_campaign_placement(monkeypatch) -> None:
    from app.api.v1 import placements

    fake = FakePlacementService()
    monkeypatch.setattr(placements, "_default_service", lambda: fake)

    payload = {
        "store_id": STORE_ID,
        "placement_type_key": "hero_main",
        "mode": "existing_section",
        "target_type": "collection",
        "target_resource_gid": "gid://shopify/Collection/1",
        "existing_placement_key": "hero",
        "existing_placement_label": "Hero principal",
        "existing_placement_size": "1440x420",
        "slot": "hero",
    }
    post = client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/placement", json=payload)
    get = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/placement")

    assert post.status_code == 200
    assert post.json()["campaign_id"] == CAMPAIGN_ID
    assert post.json()["existing_placement_key"] == "hero"
    assert get.status_code == 200
    assert get.json()["id"] == "placement-1"


def test_get_unknown_campaign_placement_returns_404(monkeypatch) -> None:
    from app.api.v1 import placements

    monkeypatch.setattr(placements, "_default_service", lambda: FakePlacementService())

    response = client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/placement")

    assert response.status_code == 404


def test_invalid_uuid_returns_422(monkeypatch) -> None:
    from app.api.v1 import placements

    monkeypatch.setattr(placements, "_default_service", lambda: FakePlacementService())

    assert client.get("/api/v1/stores/not-a-uuid/placement-types").status_code == 422
    assert client.get("/api/v1/campaigns/not-a-uuid/placement").status_code == 422


def test_invalid_body_store_id_returns_422(monkeypatch) -> None:
    from app.api.v1 import placements

    monkeypatch.setattr(placements, "_default_service", lambda: FakePlacementService())

    response = client.post(
        "/api/v1/placements/validate",
        json={"store_id": "not-a-uuid", "placement_type_key": "hero_main", "mode": "new_section", "target_type": "home"},
    )

    assert response.status_code == 422
