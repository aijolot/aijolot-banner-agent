"""Service for AI-generated banner background options (F7).

Loads the campaign's concept (from a revision) + brand context and runs the
background-options-generate skill, returning sanitized HTML/CSS options. Falls
back to deterministic brand-palette gradients when Gemini is unavailable or the
cost cap is hit (handled inside the skill).
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.campaign_revisions import CampaignRevisionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.schemas.backgrounds import BackgroundOptionsRequest, BackgroundOptionsResponse
from app.services.banners.async_run import run_coro
from app.services.banners.brand_resolver import resolve_brand_context
from app.services.supabase.client import SupabaseClientFactory
from app.workflows.banner_creation import _load_runtime_skill


class CampaignNotFound(Exception):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign '{campaign_id}' not found")
        self.campaign_id = campaign_id


class RevisionNotFound(Exception):
    def __init__(self, revision_id: str) -> None:
        super().__init__(f"revision '{revision_id}' not found")
        self.revision_id = revision_id


class CampaignRepositoryProtocol(Protocol):
    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None: ...


class RevisionRepositoryProtocol(Protocol):
    def get(self, *, revision_id: str) -> dict[str, Any] | None: ...
    def get_latest_by_campaign_id(self, *, campaign_id: str) -> dict[str, Any] | None: ...


class BackgroundOptionsService:
    def __init__(
        self,
        *,
        campaigns: CampaignRepositoryProtocol | None = None,
        revisions: RevisionRepositoryProtocol | None = None,
        settings: Settings | None = None,
        team_id: str | None = None,
    ) -> None:
        self.campaigns = campaigns
        self.revisions = revisions
        self.settings = settings
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, settings: Settings | None = None, team_id: str | None = None) -> "BackgroundOptionsService":
        return cls(
            campaigns=CampaignRepository(client),
            revisions=CampaignRevisionRepository(client),
            settings=settings,
            team_id=team_id,
        )

    def generate_options(self, campaign_id: str, request: BackgroundOptionsRequest) -> BackgroundOptionsResponse:
        campaign = self._get_campaign(campaign_id)
        revision = self._resolve_revision(campaign_id, request.revision_id)
        concept = (revision or {}).get("concept") or {}
        brand = resolve_brand_context(campaign or {"id": campaign_id})

        skill = _load_runtime_skill("background-options-generate")
        options, source = run_coro(skill.run(concept, brand, count=request.count, settings=self.settings))

        revision_id = str(revision["id"]) if revision and revision.get("id") else request.revision_id
        return BackgroundOptionsResponse(
            campaign_id=campaign_id,
            revision_id=revision_id,
            source=source,
            options=options,
        )

    def _get_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        if self.campaigns is None:
            return None
        campaign = self.campaigns.get(campaign_id=campaign_id, team_id=self.team_id)
        if campaign is None:
            raise CampaignNotFound(campaign_id)
        return campaign

    def _resolve_revision(self, campaign_id: str, revision_id: str | None) -> dict[str, Any] | None:
        if self.revisions is None:
            return None
        if revision_id:
            revision = self.revisions.get(revision_id=revision_id)
            if revision is None or str(revision.get("campaign_id")) != campaign_id:
                raise RevisionNotFound(revision_id)
            return revision
        return self.revisions.get_latest_by_campaign_id(campaign_id=campaign_id)


def _configured_service_for_team(team_id_override: str | None = None) -> BackgroundOptionsService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    has_supabase = settings.supabase_url is not None and settings.supabase_service_role_key is not None
    team_id = team_id_override or settings.supabase_team_id or settings.brand_context_team_id
    if not has_supabase_signal:
        return BackgroundOptionsService(settings=settings, team_id=team_id)
    if not has_supabase:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    if not team_id:
        raise MissingSettingsError(("SUPABASE_TEAM_ID", "BRAND_CONTEXT_TEAM_ID"))
    client = SupabaseClientFactory(settings).service_role_client()
    return BackgroundOptionsService.from_supabase_client(client, settings=settings, team_id=team_id)


def configured_service() -> BackgroundOptionsService:
    return _configured_service_for_team()


def configured_service_for_team(team_id: str) -> BackgroundOptionsService:
    return _configured_service_for_team(team_id)
