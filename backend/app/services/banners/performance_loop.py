"""Performance loop orchestration (F2): sync → detect → propose.

The ``performance_sync`` agent job iterates the team's published campaigns:
1. AnalyticsSyncService ingests a daily snapshot (real provider or honest
   synthetic series).
2. FatigueDetector evaluates CTR decay / banner age.
3. OptimizationAdvisor upserts a performance_refresh suggestion with concrete
   proposed changes; accepting it starts a refinement run with that prompt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.banners import fatigue_detector
from app.services.banners.optimization_advisor import propose_refresh
from app.services.shopify.analytics_sync import AnalyticsSyncService

PUBLISHED_STATUSES = ("published", "scheduled", "publishing")


async def run_performance_loop(
    *,
    campaigns: list[dict[str, Any]],
    performance_service: Any,
    suggestions: Any,
    provider: Any = None,
    settings: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One pass over the given campaigns. Returns a job summary."""
    now = now or datetime.now(timezone.utc)
    sync = AnalyticsSyncService(performance_service=performance_service, provider=provider)
    synced = 0
    proposed: list[str] = []
    for campaign in campaigns:
        campaign_id = str(campaign.get("id"))
        if str(campaign.get("status") or "") not in PUBLISHED_STATUSES:
            continue
        published_at = None
        for key in ("published_at", "updated_at", "created_at"):
            if campaign.get(key):
                published_at = fatigue_detector._parse_ts(campaign.get(key))
                break
        try:
            sync.sync_campaign(campaign_id, published_at=published_at, now=now)
            synced += 1
        except Exception:  # noqa: BLE001 — one campaign's sync never blocks the rest
            continue
        rows = performance_service.snapshots.list_by_campaign_id(campaign_id=campaign_id, limit=30)
        signal = fatigue_detector.evaluate(campaign_id, list(rows), published_at=published_at, now=now)
        if signal is not None:
            await propose_refresh(
                signal,
                suggestions=suggestions,
                campaign_title=str(campaign.get("title") or ""),
                settings=settings,
            )
            proposed.append(campaign_id)
    return {"campaigns_synced": synced, "refresh_proposals": proposed}


def handle_performance_sync_job(job: dict[str, Any]) -> dict[str, Any]:
    """Fase 0 job handler (kind='performance_sync')."""
    from app.core.settings import Settings
    from app.services.banners.performance_service import configured_service_for_team
    from app.services.banners.suggestion_service import configured_service_for_team as suggestions_for_team
    from app.services.banners.async_run import run_coro

    team_id = str(job.get("team_id") or "")
    settings = Settings.from_env()
    performance = configured_service_for_team(team_id)
    suggestions = suggestions_for_team(team_id)
    campaigns: list[dict[str, Any]] = []
    lister = getattr(performance.campaigns, "list", None)
    if callable(lister):
        try:
            campaigns = [dict(row) for row in lister(team_id=team_id, limit=100)]
        except Exception:  # noqa: BLE001 — no listable campaigns → empty pass
            campaigns = []
    return run_coro(
        run_performance_loop(
            campaigns=campaigns,
            performance_service=performance,
            suggestions=suggestions,
            settings=settings,
        )
    )
