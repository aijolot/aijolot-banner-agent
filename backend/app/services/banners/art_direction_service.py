from __future__ import annotations

from typing import Any, Protocol, cast

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.art_directions import ArtDirectionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.schemas.art_direction import ArtDirectionResponse, ArtDirectionUpsert
from app.services.supabase.client import SupabaseClientFactory


class CampaignNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class ArtDirectionNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"art direction for campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class ArtDirectionRepositoryProtocol(Protocol):
    def get_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...
    def upsert_for_campaign(self, *, campaign_id: str, data: dict[str, Any]) -> dict[str, Any]: ...


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...


class InMemoryArtDirectionRepository:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def get_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None:
        return self.rows.get(campaign_id)

    def upsert_for_campaign(self, *, campaign_id: str, data: dict[str, Any]) -> dict[str, Any]:
        existing = self.rows.get(campaign_id, {})
        row = {"id": existing.get("id") or f"local-art-direction-{campaign_id}", "campaign_id": campaign_id, **data}
        self.rows[campaign_id] = row
        return row


_LOCAL_ART_DIRECTION_REPOSITORY = InMemoryArtDirectionRepository()


class ArtDirectionService:
    def __init__(
        self,
        *,
        art_direction_repository: ArtDirectionRepositoryProtocol | None = None,
        campaign_repository: CampaignRepositoryProtocol | None = None,
        team_id: str | None = None,
    ) -> None:
        self.art_direction_repository = art_direction_repository or _LOCAL_ART_DIRECTION_REPOSITORY
        self.campaign_repository = campaign_repository
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str | None = None) -> "ArtDirectionService":
        return cls(
            art_direction_repository=ArtDirectionRepository(client),
            campaign_repository=CampaignRepository(client),
            team_id=team_id,
        )

    def save_art_direction(self, campaign_id: str, request: ArtDirectionUpsert) -> ArtDirectionResponse:
        self._get_campaign(campaign_id)
        row = self.art_direction_repository.upsert_for_campaign(
            campaign_id=campaign_id,
            data=request.model_dump(),
        )
        if not row:
            raise ArtDirectionNotFound(campaign_id)
        return self._response_from_record(row)

    def get_art_direction(self, campaign_id: str) -> ArtDirectionResponse:
        self._get_campaign(campaign_id)
        row = self.art_direction_repository.get_by_campaign_id(campaign_id=campaign_id)
        if row is None:
            raise ArtDirectionNotFound(campaign_id)
        return self._response_from_record(row)

    def _get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        if self.campaign_repository is None:
            return None
        campaign = self.campaign_repository.get(campaign_id=campaign_id, team_id=self.team_id)
        if campaign is None:
            raise CampaignNotFound(campaign_id)
        return campaign

    @staticmethod
    def _response_from_record(row: dict[str, Any]) -> ArtDirectionResponse:
        fold_percentage = row.get("fold_percentage")
        return ArtDirectionResponse(
            id=str(row["id"]),
            campaign_id=str(row["campaign_id"]),
            background_mode=cast(Any, row["background_mode"]),
            hero_style_key=cast(str | None, row.get("hero_style_key")),
            model_key=cast(str | None, row.get("model_key")),
            custom_model=dict(row.get("custom_model") or {}),
            fold_percentage=int(cast(Any, fold_percentage if fold_percentage is not None else 55)),
            layout_hints=dict(row.get("layout_hints") or {}),
            created_at=str(row["created_at"]) if row.get("created_at") is not None else None,
            updated_at=str(row["updated_at"]) if row.get("updated_at") is not None else None,
        )


def configured_service() -> ArtDirectionService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        return ArtDirectionService(team_id=team_id)
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return ArtDirectionService.from_supabase_client(client, team_id=team_id)
