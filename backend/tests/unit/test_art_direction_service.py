from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.art_direction import ArtDirectionUpsert
from app.services.banners.art_direction_service import (
    ArtDirectionNotFound,
    ArtDirectionService,
    CampaignNotFound,
)

CAMPAIGN_ID = "00000000-0000-0000-0000-000000000301"


class MemoryArtDirectionRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def get_by_campaign_id(self, *, campaign_id: str) -> dict | None:
        return self.rows.get(campaign_id)

    def upsert_for_campaign(self, *, campaign_id: str, data: dict) -> dict:
        existing = self.rows.get(campaign_id, {})
        row = {"id": existing.get("id") or "art-direction-1", "campaign_id": campaign_id, **data}
        self.rows[campaign_id] = row
        return row


class FakeCampaignRepository:
    def __init__(self, *, exists: bool = True, status: str = "brief_ready") -> None:
        self.exists = exists
        self.status = status
        self.updated: list[dict] = []

    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict | None:
        if not self.exists:
            return None
        return {"id": campaign_id, "team_id": team_id or "team-1", "status": self.status}

    def update(self, *, campaign_id: str, data: dict, team_id: str | None = None) -> dict | None:
        self.updated.append({"campaign_id": campaign_id, "data": data, "team_id": team_id})
        self.status = data.get("status", self.status)
        return self.get(campaign_id=campaign_id, team_id=team_id)


@pytest.fixture
def service() -> ArtDirectionService:
    return ArtDirectionService(
        art_direction_repository=MemoryArtDirectionRepository(),
        campaign_repository=FakeCampaignRepository(),
        team_id="team-1",
    )


def test_schema_validates_background_mode_and_fold_range() -> None:
    with pytest.raises(ValidationError):
        ArtDirectionUpsert(background_mode="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ArtDirectionUpsert(background_mode="hero", fold_percentage=101)
    with pytest.raises(ValidationError):
        ArtDirectionUpsert(background_mode="usage", layout_hints=[])  # type: ignore[arg-type]


def test_schema_normalizes_blank_optional_keys_and_preserves_custom_model_metadata() -> None:
    request = ArtDirectionUpsert(
        background_mode="hero",
        hero_style_key="  ",
        model_key=" model-a ",
        custom_model={"persona": "metadata-only"},
    )

    assert request.hero_style_key is None
    assert request.model_key == "model-a"
    assert request.custom_model == {"persona": "metadata-only"}


def test_saves_and_reads_art_direction(service: ArtDirectionService) -> None:
    saved = service.save_art_direction(
        CAMPAIGN_ID,
        ArtDirectionUpsert(
            background_mode="hero",
            hero_style_key="luxury-gradient",
            model_key="seed-model",
            custom_model={"description": "metadata only"},
            fold_percentage=60,
            layout_hints={"safe_zone": "left"},
        ),
    )

    assert saved.id == "art-direction-1"
    assert saved.campaign_id == CAMPAIGN_ID
    assert saved.background_mode == "hero"
    assert saved.fold_percentage == 60
    assert service.get_art_direction(CAMPAIGN_ID).layout_hints == {"safe_zone": "left"}


def test_upsert_updates_existing_art_direction() -> None:
    repo = MemoryArtDirectionRepository()
    service = ArtDirectionService(art_direction_repository=repo)

    first = service.save_art_direction(CAMPAIGN_ID, ArtDirectionUpsert(background_mode="hero", fold_percentage=40))
    second = service.save_art_direction(CAMPAIGN_ID, ArtDirectionUpsert(background_mode="usage", fold_percentage=70))

    assert second.id == first.id
    assert second.background_mode == "usage"
    assert second.fold_percentage == 70
    assert len(repo.rows) == 1


def test_response_converts_timestamps_to_strings() -> None:
    repo = MemoryArtDirectionRepository()
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    updated_at = "2026-01-02T03:05:06+00:00"
    repo.rows[CAMPAIGN_ID] = {
        "id": "art-direction-1",
        "campaign_id": CAMPAIGN_ID,
        "background_mode": "hero",
        "created_at": created_at,
        "updated_at": updated_at,
    }
    service = ArtDirectionService(art_direction_repository=repo)

    response = service.get_art_direction(CAMPAIGN_ID)

    assert response.created_at == str(created_at)
    assert response.updated_at == updated_at


def test_save_unknown_campaign_raises() -> None:
    service = ArtDirectionService(
        art_direction_repository=MemoryArtDirectionRepository(),
        campaign_repository=FakeCampaignRepository(exists=False),
    )

    with pytest.raises(CampaignNotFound):
        service.save_art_direction(CAMPAIGN_ID, ArtDirectionUpsert(background_mode="hero"))


def test_get_missing_art_direction_raises(service: ArtDirectionService) -> None:
    with pytest.raises(ArtDirectionNotFound):
        service.get_art_direction(CAMPAIGN_ID)


@pytest.mark.parametrize("status", ["brief_ready", "needs_review", "changes_requested", "generating"])
def test_save_does_not_mutate_campaign_status(status: str) -> None:
    campaign_repo = FakeCampaignRepository(status=status)
    service = ArtDirectionService(
        art_direction_repository=MemoryArtDirectionRepository(),
        campaign_repository=campaign_repo,
        team_id="team-1",
    )

    service.save_art_direction(CAMPAIGN_ID, ArtDirectionUpsert(background_mode="usage"))

    assert campaign_repo.updated == []
    assert campaign_repo.status == status
