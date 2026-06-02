from __future__ import annotations

import pytest

from app.schemas.placements import CampaignPlacementUpsert, PlacementValidateRequest
from app.services.banners.placement_service import (
    CampaignNotFound,
    InvalidPlacement,
    PlacementService,
    PlacementTypeNotFound,
)
from app.services.shopify.resource_service import ShopifyResourceService, SeedShopifyResourceCacheRepository, SeedStoreRepository

STORE_ID = "00000000-0000-0000-0000-000000000101"
CAMPAIGN_ID = "00000000-0000-0000-0000-000000000301"


class MemoryPlacementRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def get_by_campaign_id(self, *, campaign_id: str) -> dict | None:
        return self.rows.get(campaign_id)

    def upsert_for_campaign(self, *, campaign_id: str, data: dict) -> dict:
        row = {"id": "placement-1", "campaign_id": campaign_id, **data}
        self.rows[campaign_id] = row
        return row


class FakeCampaignRepository:
    def __init__(self, exists: bool = True, store_id: str = STORE_ID) -> None:
        self.exists = exists
        self.store_id = store_id

    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict | None:
        if not self.exists:
            return None
        return {"id": campaign_id, "store_id": self.store_id, "team_id": team_id or "team-1"}


@pytest.fixture
def service() -> PlacementService:
    resource_service = ShopifyResourceService(
        store_repository=SeedStoreRepository(),
        resource_repository=SeedShopifyResourceCacheRepository(),
    )
    return PlacementService(
        resource_service=resource_service,
        campaign_repository=FakeCampaignRepository(),
        campaign_placement_repository=MemoryPlacementRepository(),
    )


def test_lists_seeded_placement_types(service: PlacementService) -> None:
    types = service.list_placement_types(STORE_ID)

    keys = {item.key for item in types}
    assert "hero_main" in keys
    assert "search_results_banner" in keys
    assert all(item.is_active for item in types)


def test_lists_targets_for_placement_type_from_cache(service: PlacementService) -> None:
    targets = service.list_targets(STORE_ID, "collection_header")

    assert set(targets.keys()) == {"collection"}
    assert targets["collection"][0].shopify_gid == "gid://shopify/Collection/1"


def test_validates_existing_section_target_and_slot(service: PlacementService) -> None:
    result = service.validate(
        PlacementValidateRequest(
            store_id=STORE_ID,
            placement_type_key="collection_header",
            mode="existing_section",
            target_type="collection",
            target_resource_gid="gid://shopify/Collection/1",
            existing_placement_key="coll_top",
            existing_placement_label="Cabecera de colección",
            existing_placement_size="1440x320",
            slot="coll_top",
        )
    )

    assert result.valid is True
    assert result.placement.target_handle == "fragancias"
    assert result.placement.target_title == "Fragancias"


def test_rejects_unsupported_target_for_placement_type(service: PlacementService) -> None:
    with pytest.raises(InvalidPlacement, match="does not support target"):
        service.validate(
            PlacementValidateRequest(
                store_id=STORE_ID,
                placement_type_key="collection_header",
                mode="new_section",
                target_type="product",
                target_resource_gid="gid://shopify/Product/1001",
            )
        )


def test_search_result_placement_validates_without_gid(service: PlacementService) -> None:
    result = service.validate(
        PlacementValidateRequest(
            store_id=STORE_ID,
            placement_type_key="search_results_banner",
            mode="new_section",
            target_type="search",
            target_handle="q:hugo-boss",
            layout_json={"cols": [{"rows": 1, "w": 1, "align": "center"}]},
        )
    )

    assert result.valid is True
    assert result.placement.target_type == "search"


def test_rejects_search_target_with_resource_gid(service: PlacementService) -> None:
    with pytest.raises(InvalidPlacement, match="target_resource_gid"):
        service.validate(
            PlacementValidateRequest(
                store_id=STORE_ID,
                placement_type_key="search_results_banner",
                mode="new_section",
                target_type="search",
                target_resource_gid="gid://shopify/Product/1001",
            )
        )


def test_rejects_home_target_with_resource_handle(service: PlacementService) -> None:
    with pytest.raises(InvalidPlacement, match="resource identifiers"):
        service.validate(
            PlacementValidateRequest(
                store_id=STORE_ID,
                placement_type_key="hero_main",
                mode="new_section",
                target_type="home",
                target_handle="stale-handle",
            )
        )


def test_unknown_placement_type_raises(service: PlacementService) -> None:
    with pytest.raises(PlacementTypeNotFound):
        service.list_targets(STORE_ID, "missing")


def test_saves_and_reads_campaign_placement(service: PlacementService) -> None:
    saved = service.save_campaign_placement(
        CAMPAIGN_ID,
        CampaignPlacementUpsert(
            store_id=STORE_ID,
            placement_type_key="hero_main",
            mode="new_section",
            target_type="home",
            slot="hero",
            layout_json={"cols": [{"rows": 2, "w": 1, "align": "center"}]},
        ),
    )

    assert saved.campaign_id == CAMPAIGN_ID
    assert saved.placement_type_key == "hero_main"
    assert saved.layout_json["cols"][0]["rows"] == 2
    assert service.get_campaign_placement(CAMPAIGN_ID).id == saved.id


def test_save_unknown_campaign_raises() -> None:
    service = PlacementService(campaign_repository=FakeCampaignRepository(exists=False), campaign_placement_repository=MemoryPlacementRepository())

    with pytest.raises(CampaignNotFound):
        service.save_campaign_placement(
            CAMPAIGN_ID,
            CampaignPlacementUpsert(
                store_id=STORE_ID,
                placement_type_key="hero_main",
                mode="new_section",
                target_type="home",
            ),
        )
