"""Daily USD cost guard for Gemini calls (text + image).

Process-local accumulator that fails closed when the configured
``DAILY_COST_CAP_USD`` is reached. Skills consult :meth:`check_and_reserve`
before a paid Gemini call and fall back to their deterministic path when the
reservation is denied. Mirrors the in-memory style of ``UsageGuardService``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

from app.core.settings import Settings


@dataclass(frozen=True, slots=True)
class CostGuardResult:
    allowed: bool
    estimated_usd: float
    spent_usd: float
    cap_usd: float
    remaining_usd: float
    reason: str | None = None

    def to_metadata(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "estimated_usd": self.estimated_usd,
            "spent_usd": round(self.spent_usd, 6),
            "cap_usd": self.cap_usd,
            "remaining_usd": round(self.remaining_usd, 6),
            "reason": self.reason,
        }


class CostGuard:
    """In-memory per-day spend accumulator keyed by UTC date."""

    def __init__(self, *, cap_usd: float) -> None:
        self._cap_usd = max(0.0, float(cap_usd))
        self._spent: dict[str, float] = {}
        self._lock = Lock()

    @staticmethod
    def _day_key(now: datetime) -> str:
        return now.astimezone(UTC).strftime("%Y-%m-%d")

    def check_and_reserve(self, estimated_usd: float, *, now: datetime | None = None) -> CostGuardResult:
        estimate = max(0.0, float(estimated_usd))
        timestamp = now or datetime.now(UTC)
        day = self._day_key(timestamp)
        with self._lock:
            spent = self._spent.get(day, 0.0)
            # A cap of 0 disables the guard (unbounded) to keep tests/demos simple.
            if self._cap_usd <= 0 or (spent + estimate) <= self._cap_usd:
                self._spent[day] = spent + estimate
                allowed, reason = True, None
            else:
                allowed = False
                reason = (
                    f"Daily Gemini cost cap reached: spent ${spent:.4f} + est ${estimate:.4f} "
                    f"exceeds cap ${self._cap_usd:.2f}"
                )
            remaining = float("inf") if self._cap_usd <= 0 else max(0.0, self._cap_usd - self._spent.get(day, spent))
        return CostGuardResult(
            allowed=allowed,
            estimated_usd=estimate,
            spent_usd=self._spent.get(day, spent),
            cap_usd=self._cap_usd,
            remaining_usd=remaining,
            reason=reason,
        )

    def clear(self) -> None:
        with self._lock:
            self._spent.clear()


_DEFAULT_GUARD: CostGuard | None = None


def get_default_cost_guard(settings: Settings | None = None) -> CostGuard:
    global _DEFAULT_GUARD
    if _DEFAULT_GUARD is None:
        resolved = settings or Settings.from_env()
        _DEFAULT_GUARD = CostGuard(cap_usd=resolved.daily_cost_cap_usd)
    return _DEFAULT_GUARD


def reset_default_cost_guard() -> None:
    """Clear process-local cost state for deterministic tests/demos."""

    global _DEFAULT_GUARD
    if _DEFAULT_GUARD is not None:
        _DEFAULT_GUARD.clear()
    _DEFAULT_GUARD = None
