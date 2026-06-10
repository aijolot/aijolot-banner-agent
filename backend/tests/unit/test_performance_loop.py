"""F2 — performance loop: fatigue detection, honest sync sources, refresh proposals."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.services.banners.fatigue_detector import evaluate
from app.services.banners.performance_loop import run_performance_loop
from app.services.banners.suggestion_service import InMemoryAgentSuggestions, SuggestionService
from app.services.shopify.analytics_sync import AnalyticsSyncService, synthetic_metrics

NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
TEAM = "team-perf"
CAMPAIGN = "00000000-0000-0000-0000-0000000009aa"


def _snap(days_ago: float, ctr: float) -> dict:
    return {"window_end": (NOW - timedelta(days=days_ago)).isoformat(), "ctr": ctr}


# --- fatigue detector ---------------------------------------------------------


def test_clear_ctr_decay_is_flagged() -> None:
    snaps = [_snap(10, 0.050), _snap(7, 0.042), _snap(4, 0.034), _snap(1, 0.027)]
    signal = evaluate(CAMPAIGN, snaps, now=NOW)
    assert signal is not None and signal.kind == "ctr_decay"
    assert signal.metrics["decay_pct"] >= 15
    assert "CTR" in signal.reason


def test_noisy_flat_series_is_not_flagged() -> None:
    snaps = [_snap(10, 0.041), _snap(7, 0.043), _snap(4, 0.040), _snap(1, 0.042)]
    assert evaluate(CAMPAIGN, snaps, now=NOW) is None


def test_insufficient_samples_fall_back_to_age_rule() -> None:
    snaps = [_snap(1, 0.02)]
    old_publish = NOW - timedelta(days=45)
    signal = evaluate(CAMPAIGN, snaps, published_at=old_publish.isoformat(), now=NOW)
    assert signal is not None and signal.kind == "banner_age"
    assert signal.metrics["banner_age_days"] == 45


def test_fresh_banner_with_few_samples_is_quiet() -> None:
    snaps = [_snap(1, 0.04)]
    publish = NOW - timedelta(days=3)
    assert evaluate(CAMPAIGN, snaps, published_at=publish.isoformat(), now=NOW) is None


# --- analytics sync -------------------------------------------------------------


class _PerfStub:
    def __init__(self) -> None:
        self.created: list = []

    def create_snapshot(self, campaign_id, request):
        self.created.append((campaign_id, request))
        return request

    class snapshots:  # noqa: N801 — protocol shim
        ...


def test_synthetic_series_is_deterministic_and_decays() -> None:
    early = synthetic_metrics(CAMPAIGN, day_index=0)
    late = synthetic_metrics(CAMPAIGN, day_index=20)
    again = synthetic_metrics(CAMPAIGN, day_index=20)
    assert late == again  # same campaign+day → same numbers (demo-stable)
    assert late["clicks"] < early["clicks"]


def test_sync_labels_sources_honestly() -> None:
    perf = _PerfStub()
    no_provider = AnalyticsSyncService(performance_service=perf)
    no_provider.sync_campaign(CAMPAIGN, published_at=NOW - timedelta(days=5), now=NOW)
    assert perf.created[-1][1].source == "agent"  # synthetic, never claims 'shopify'

    class _Provider:
        def fetch(self, **kwargs):
            return {"impressions": 1000, "clicks": 50, "conversions": 5}

    with_provider = AnalyticsSyncService(performance_service=perf, provider=_Provider())
    with_provider.sync_campaign(CAMPAIGN, now=NOW)
    assert perf.created[-1][1].source == "shopify"


# --- end-to-end loop -------------------------------------------------------------


class _Snapshots:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def list_by_campaign_id(self, *, campaign_id, limit=30):
        return [r for r in self.rows if r["campaign_id"] == campaign_id][-limit:]

    def create(self, *, data):
        self.rows.append(dict(data))
        return dict(data)


class _PerfService:
    def __init__(self) -> None:
        self.snapshots = _Snapshots()

    def create_snapshot(self, campaign_id, request):
        from app.schemas.performance import PerformanceSnapshotResponse

        row = {"id": f"snap-{len(self.snapshots.rows)}", "campaign_id": campaign_id, **request.model_dump()}
        self.snapshots.create(data=row)
        return PerformanceSnapshotResponse.model_validate(row)


def test_loop_syncs_detects_and_proposes_refresh() -> None:
    perf = _PerfService()
    # Seed a decaying history so today's sync completes a fatigued series.
    for days_ago, ctr in ((9, 0.05), (6, 0.041), (3, 0.031)):
        perf.snapshots.create(data={"campaign_id": CAMPAIGN, "window_end": (NOW - timedelta(days=days_ago)).isoformat(), "ctr": 0.0 + ctr})
    suggestions = SuggestionService(suggestions=InMemoryAgentSuggestions(), team_id=TEAM)
    campaigns = [{"id": CAMPAIGN, "title": "Hero verano", "status": "published",
                  "published_at": (NOW - timedelta(days=20)).isoformat()}]

    summary = asyncio.run(run_performance_loop(
        campaigns=campaigns, performance_service=perf, suggestions=suggestions, now=NOW,
    ))

    assert summary["campaigns_synced"] == 1
    assert summary["refresh_proposals"] == [CAMPAIGN]
    pending = suggestions.list()
    assert len(pending) == 1
    refresh = pending[0]
    assert refresh.kind == "performance_refresh"
    assert refresh.campaign_id == CAMPAIGN
    assert refresh.payload["proposed_changes"]
    assert "Refresca el banner" in refresh.payload["refresh_prompt"]
    # Idempotent on the next pass (same trigger kind → same dedupe key).
    asyncio.run(run_performance_loop(campaigns=campaigns, performance_service=perf, suggestions=suggestions, now=NOW))
    assert len(suggestions.list()) == 1


def test_draft_campaigns_are_skipped() -> None:
    perf = _PerfService()
    suggestions = SuggestionService(suggestions=InMemoryAgentSuggestions(), team_id=TEAM)
    summary = asyncio.run(run_performance_loop(
        campaigns=[{"id": CAMPAIGN, "status": "draft"}], performance_service=perf, suggestions=suggestions, now=NOW,
    ))
    assert summary["campaigns_synced"] == 0
