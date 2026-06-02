from __future__ import annotations

import itertools
from datetime import datetime, timezone
from typing import Any

from app.core.settings import MissingSettingsError, Settings
from app.db.repositories.campaign_revisions import CampaignRevisionRepository
from app.db.repositories.campaigns import CampaignRepository
from app.db.repositories.optimization_insights import OptimizationInsightRepository
from app.db.repositories.optimization_proposals import OptimizationProposalRepository
from app.db.repositories.performance_snapshots import PerformanceSnapshotRepository
from app.schemas.performance import (
    CampaignPerformanceResponse,
    OptimizationInsightResponse,
    OptimizationProposalCreate,
    OptimizationProposalResponse,
    PerformanceSnapshotCreate,
    PerformanceSnapshotResponse,
)
from app.services.supabase.client import SupabaseClientFactory


class PerformanceError(Exception):
    pass


class CampaignNotFound(PerformanceError):
    def __init__(self, campaign_id: str) -> None:
        super().__init__(f"campaign {campaign_id} not found")


class InvalidPerformanceMetric(PerformanceError):
    pass


class InMemoryPerformanceSnapshots:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._ids = itertools.count(1)

    def list_by_campaign_id(self, *, campaign_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [dict(row) for row in reversed(self.rows) if row["campaign_id"] == campaign_id][:limit]

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        row = {"id": f"perf_snapshot_{next(self._ids):04d}", "created_at": _now(), **data}
        self.rows.append(row)
        return dict(row)


class InMemoryOptimizationInsights:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def list_for_team_and_campaign(self, *, team_id: str, campaign_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = [row for row in self.rows if row.get("team_id") == team_id and row.get("campaign_id") in (None, campaign_id)]
        return [dict(row) for row in rows[:limit]]


class InMemoryOptimizationProposals:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._ids = itertools.count(1)

    def list_by_campaign_id(self, *, campaign_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return [dict(row) for row in reversed(self.rows) if row["campaign_id"] == campaign_id][:limit]

    def create(self, *, data: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        row = {"id": f"optimization_proposal_{next(self._ids):04d}", "status": "draft", "created_at": now, "updated_at": now, **data}
        self.rows.append(row)
        return dict(row)


class InMemoryCampaignLookup:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def get(self, *, campaign_id: str, team_id: str | None = None) -> dict[str, Any] | None:
        row = self.rows.get(campaign_id)
        if row and (team_id is None or row.get("team_id") == team_id):
            return dict(row)
        return None


class InMemoryRevisionLookup:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def get(self, *, revision_id: str) -> dict[str, Any] | None:
        row = self.rows.get(revision_id)
        return dict(row) if row else None


_team_memory: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


class PerformanceService:
    def __init__(self, *, campaigns: Any, revisions: Any, snapshots: Any, insights: Any, proposals: Any, team_id: str | None = None) -> None:
        self.campaigns = campaigns
        self.revisions = revisions
        self.snapshots = snapshots
        self.insights = insights
        self.proposals = proposals
        self.team_id = team_id

    @classmethod
    def from_supabase_client(cls, client: Any, *, team_id: str) -> "PerformanceService":
        return cls(
            campaigns=CampaignRepository(client),
            revisions=CampaignRevisionRepository(client),
            snapshots=PerformanceSnapshotRepository(client),
            insights=OptimizationInsightRepository(client),
            proposals=OptimizationProposalRepository(client),
            team_id=team_id,
        )

    def get_campaign_performance(self, campaign_id: str, *, limit: int = 20) -> CampaignPerformanceResponse:
        self._get_campaign(campaign_id)
        snapshots = [PerformanceSnapshotResponse.model_validate(row) for row in self.snapshots.list_by_campaign_id(campaign_id=campaign_id, limit=limit)]
        insights = [OptimizationInsightResponse.model_validate(row) for row in self.insights.list_for_team_and_campaign(team_id=self.team_id or "", campaign_id=campaign_id, limit=limit)]
        proposals = [OptimizationProposalResponse.model_validate(row) for row in self.proposals.list_by_campaign_id(campaign_id=campaign_id, limit=limit)]
        return CampaignPerformanceResponse(
            campaign_id=campaign_id,
            latest_snapshot=snapshots[0] if snapshots else None,
            snapshots=snapshots,
            insights=insights,
            proposals=proposals,
        )

    def create_snapshot(self, campaign_id: str, request: PerformanceSnapshotCreate) -> PerformanceSnapshotResponse:
        campaign = self._get_campaign(campaign_id)
        revision_id = request.revision_id or campaign.get("selected_revision_id")
        self._require_campaign_revision(campaign_id, revision_id)
        ctr = request.ctr if request.ctr is not None else _rate(request.clicks, request.impressions)
        conversion_rate = request.conversion_rate if request.conversion_rate is not None else _rate(request.conversions, request.clicks)
        self._validate_metrics(request, ctr=ctr, conversion_rate=conversion_rate)
        row = self.snapshots.create(
            data={
                "campaign_id": campaign_id,
                "revision_id": revision_id,
                "source": request.source,
                "window_start": request.window_start,
                "window_end": request.window_end,
                "impressions": request.impressions,
                "clicks": request.clicks,
                "ctr": ctr,
                "conversions": request.conversions,
                "conversion_rate": conversion_rate,
                "load_p75_ms": request.load_p75_ms,
                "weight_saved_pct": request.weight_saved_pct,
                "segment_breakdown": request.segment_breakdown,
                "trend": request.trend,
            }
        )
        return PerformanceSnapshotResponse.model_validate(row)

    def create_proposal(self, campaign_id: str, request: OptimizationProposalCreate) -> OptimizationProposalResponse:
        self._get_campaign(campaign_id)
        self._require_campaign_revision(campaign_id, request.source_revision_id)
        self._require_campaign_revision(campaign_id, request.proposed_revision_id)
        row = self.proposals.create(data={"campaign_id": campaign_id, **request.model_dump()})
        return OptimizationProposalResponse.model_validate(row)

    def _get_campaign(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.campaigns.get(campaign_id=campaign_id, team_id=self.team_id)
        if not campaign:
            raise CampaignNotFound(campaign_id)
        return dict(campaign)

    def _require_campaign_revision(self, campaign_id: str, revision_id: str | None) -> None:
        if not revision_id:
            return
        revision = self.revisions.get(revision_id=revision_id)
        if not revision or revision.get("campaign_id") != campaign_id:
            raise CampaignNotFound(campaign_id)

    @staticmethod
    def _validate_metrics(request: PerformanceSnapshotCreate, *, ctr: float, conversion_rate: float) -> None:
        if request.clicks > request.impressions:
            raise InvalidPerformanceMetric("clicks cannot exceed impressions")
        if request.conversions > request.clicks:
            raise InvalidPerformanceMetric("conversions cannot exceed clicks")
        if not 0 <= ctr <= 1:
            raise InvalidPerformanceMetric("ctr must be between 0 and 1")
        if not 0 <= conversion_rate <= 1:
            raise InvalidPerformanceMetric("conversion_rate must be between 0 and 1")
        if request.weight_saved_pct is not None and not 0 <= request.weight_saved_pct <= 1:
            raise InvalidPerformanceMetric("weight_saved_pct must be between 0 and 1")


def _memory_for_team(team_id: str) -> dict[str, Any]:
    if team_id not in _team_memory:
        _team_memory[team_id] = {
            "campaigns": InMemoryCampaignLookup(),
            "revisions": InMemoryRevisionLookup(),
            "snapshots": InMemoryPerformanceSnapshots(),
            "insights": InMemoryOptimizationInsights(),
            "proposals": InMemoryOptimizationProposals(),
        }
    return _team_memory[team_id]


def _configured_service_for_team(team_id: str) -> PerformanceService:
    settings = Settings.from_env()
    has_supabase_signal = any((settings.supabase_url, settings.supabase_service_role_key, settings.supabase_team_id))
    if not has_supabase_signal:
        return PerformanceService(team_id=team_id, **_memory_for_team(team_id))
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise MissingSettingsError(("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"))
    client = SupabaseClientFactory(settings).service_role_client()
    return PerformanceService.from_supabase_client(client, team_id=team_id)


def configured_service_for_team(team_id: str) -> PerformanceService:
    return _configured_service_for_team(team_id)
