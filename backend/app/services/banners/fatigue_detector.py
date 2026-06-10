"""FatigueDetector (F2) — deterministic banner-fatigue detection. No LLM.

Fits a simple linear regression over the recent CTR series and flags:
  - ctr_decay:   fitted CTR dropped >= threshold % across the window (n >= 3)
  - banner_age:  the selected revision has been live longer than max_age_days

Pure functions over snapshot dicts so it works identically against Supabase
rows, in-memory repos, and synthetic demo data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

DECAY_THRESHOLD_PCT = 15.0
MIN_SNAPSHOTS = 3
WINDOW_DAYS = 14
MAX_AGE_DAYS = 30


@dataclass(frozen=True)
class FatigueSignal:
    campaign_id: str
    kind: str  # "ctr_decay" | "banner_age"
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _linear_slope(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Least-squares (slope, intercept) for [(x, y)]."""
    n = len(points)
    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n
    denom = sum((p[0] - mean_x) ** 2 for p in points)
    if denom == 0:
        return 0.0, mean_y
    slope = sum((p[0] - mean_x) * (p[1] - mean_y) for p in points) / denom
    return slope, mean_y - slope * mean_x


def evaluate(
    campaign_id: str,
    snapshots: list[dict[str, Any]],
    *,
    published_at: Any = None,
    now: datetime | None = None,
    decay_threshold_pct: float = DECAY_THRESHOLD_PCT,
    window_days: int = WINDOW_DAYS,
    max_age_days: int = MAX_AGE_DAYS,
) -> FatigueSignal | None:
    """Return the strongest fatigue signal for the campaign, or None."""
    now = now or datetime.now(timezone.utc)

    # --- CTR decay over the recent window ------------------------------------
    series: list[tuple[float, float]] = []
    for snap in snapshots:
        ts = _parse_ts(snap.get("window_end") or snap.get("created_at"))
        ctr = snap.get("ctr")
        if ts is None or not isinstance(ctr, (int, float)):
            continue
        age_days = (now - ts).total_seconds() / 86400.0
        if age_days <= window_days + 1:
            series.append((-age_days, float(ctr)))  # x grows toward "now"
    if len(series) >= MIN_SNAPSHOTS:
        series.sort(key=lambda p: p[0])
        slope, intercept = _linear_slope(series)
        x_first, x_last = series[0][0], series[-1][0]
        fitted_first = slope * x_first + intercept
        fitted_last = slope * x_last + intercept
        if fitted_first > 0 and slope < 0:
            decay_pct = (fitted_first - fitted_last) / fitted_first * 100.0
            if decay_pct >= decay_threshold_pct:
                return FatigueSignal(
                    campaign_id=campaign_id,
                    kind="ctr_decay",
                    reason=(
                        f"El CTR cayó ~{decay_pct:.0f}% en los últimos {window_days} días "
                        f"({fitted_first:.2%} → {fitted_last:.2%})."
                    ),
                    metrics={
                        "decay_pct": round(decay_pct, 1),
                        "window_days": window_days,
                        "ctr_start": round(fitted_first, 4),
                        "ctr_end": round(fitted_last, 4),
                        "samples": len(series),
                    },
                )

    # --- banner age ------------------------------------------------------------
    published = _parse_ts(published_at)
    if published is not None:
        age_days = (now - published).days
        if age_days > max_age_days:
            return FatigueSignal(
                campaign_id=campaign_id,
                kind="banner_age",
                reason=f"El banner lleva {age_days} días publicado sin refresco (umbral: {max_age_days}).",
                metrics={"banner_age_days": age_days, "max_age_days": max_age_days},
            )
    return None
