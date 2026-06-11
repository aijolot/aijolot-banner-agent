"""AnalyticsSyncService (F2) — banner metrics ingestion.

Provider seam: a real ``MetricsProvider`` (Shopify Admin / GA4) plugs in when
credentials exist; without one, a DETERMINISTIC synthetic series (seeded by
campaign id, decaying over days-since-publish) keeps the whole performance loop
demo-able. The snapshot ``source`` is honest: 'shopify' only for real provider
data, 'agent' for the synthetic series.

Shopify caveat: the Admin API has no banner-level CTR; a real provider should
attribute via UTM-tagged destination URLs (the publisher already appends them)
against orders/sessions reports. That implementation slots into
``MetricsProvider.fetch`` without touching the loop.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


class MetricsProvider(Protocol):
    def fetch(self, *, campaign_id: str, window_start: datetime, window_end: datetime) -> dict[str, Any] | None:
        """Return {impressions, clicks, conversions} for the window, or None."""
        ...


def _seed_int(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def synthetic_metrics(campaign_id: str, *, day_index: int) -> dict[str, Any]:
    """Deterministic decaying series: same campaign → same curve, every run.

    CTR starts ~4-6% (seeded) and decays ~3%/day so the fatigue detector has a
    realistic signal to find after ~2 weeks.
    """
    seed = _seed_int(campaign_id)
    base_impressions = 800 + (seed % 400)
    base_ctr = 0.04 + (seed % 20) / 1000.0  # 4.0% – 5.9%
    decay = max(0.25, 1.0 - 0.03 * day_index)
    impressions = int(base_impressions * (0.95 + ((seed >> 3) % 10) / 100.0))
    ctr = base_ctr * decay
    clicks = max(0, int(impressions * ctr))
    conversions = max(0, int(clicks * 0.08))
    return {"impressions": impressions, "clicks": clicks, "conversions": conversions}


class AnalyticsSyncService:
    def __init__(self, *, performance_service: Any, provider: MetricsProvider | None = None) -> None:
        self.performance = performance_service
        self.provider = provider

    def sync_campaign(
        self,
        campaign_id: str,
        *,
        published_at: datetime | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Ingest one daily snapshot for the campaign. Returns the snapshot row."""
        from app.schemas.performance import PerformanceSnapshotCreate

        now = now or datetime.now(timezone.utc)
        window_start = now - timedelta(days=1)
        metrics: dict[str, Any] | None = None
        source = "shopify"
        if self.provider is not None:
            try:
                metrics = self.provider.fetch(campaign_id=campaign_id, window_start=window_start, window_end=now)
            except Exception:  # noqa: BLE001 — provider failure → synthetic fallback
                metrics = None
        if metrics is None:
            day_index = max(0, (now - published_at).days) if published_at else 0
            metrics = synthetic_metrics(campaign_id, day_index=day_index)
            source = "agent"  # honest: not real store analytics
        impressions = int(metrics.get("impressions") or 0)
        clicks = min(int(metrics.get("clicks") or 0), impressions)
        conversions = min(int(metrics.get("conversions") or 0), clicks)
        request = PerformanceSnapshotCreate(
            source=source,
            window_start=window_start.isoformat(),
            window_end=now.isoformat(),
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            ctr=(clicks / impressions) if impressions else 0.0,
            conversion_rate=(conversions / clicks) if clicks else 0.0,
        )
        snapshot = self.performance.create_snapshot(campaign_id, request)
        return snapshot.model_dump() if hasattr(snapshot, "model_dump") else dict(snapshot)
